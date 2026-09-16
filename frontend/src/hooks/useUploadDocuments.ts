import { useState } from "react";
import { uploadDocument, uploadDocumentFile } from "@/services/documentService";
import type { UploadFileResult } from "@/types/api";
import {
  getRelativePath,
  isSupportedBinaryUploadFile,
  isSupportedUploadFile,
  readFileAsText,
} from "@/utils/file";

interface UploadDocumentsInput {
  kbId: string;
  files: File[];
}

export function useUploadDocuments() {
  const [isUploading, setIsUploading] = useState(false);
  const [currentFile, setCurrentFile] = useState<string | null>(null);
  const [results, setResults] = useState<UploadFileResult[]>([]);

  async function uploadSequentially({ kbId, files }: UploadDocumentsInput) {
    setIsUploading(true);
    setResults([]);

    const nextResults: UploadFileResult[] = [];

    for (const file of files) {
      const relativePath = getRelativePath(file);
      setCurrentFile(relativePath);

      if (!isSupportedUploadFile(file)) {
        const result: UploadFileResult = {
          fileName: file.name,
          relativePath,
          status: "failed",
          message: "仅支持 .txt、.md、.pdf、.docx 文件",
        };
        nextResults.push(result);
        setResults([...nextResults]);
        continue;
      }

      try {
        let data;
        if (isSupportedBinaryUploadFile(file)) {
          const formData = new FormData();
          formData.append("kb_id", kbId);
          formData.append("title", file.name);
          formData.append("file", file);
          data = await uploadDocumentFile(formData);
        } else {
          const content = await readFileAsText(file);
          data = await uploadDocument({
            kb_id: kbId,
            title: file.name,
            content,
          });
        }
        const result: UploadFileResult = {
          fileName: file.name,
          relativePath,
          status: "submitted",
          documentId: data.document_id,
          chunkCount: data.chunk_count,
          message: "已提交，正在后台索引",
        };
        nextResults.push(result);
      } catch (error) {
        const result: UploadFileResult = {
          fileName: file.name,
          relativePath,
          status: "failed",
          message: error instanceof Error ? error.message : "上传失败",
        };
        nextResults.push(result);
      }

      setResults([...nextResults]);
    }

    setCurrentFile(null);
    setIsUploading(false);
    return nextResults;
  }

  return {
    currentFile,
    isUploading,
    results,
    uploadSequentially,
    resetUploadState() {
      setCurrentFile(null);
      setResults([]);
    },
  };
}
