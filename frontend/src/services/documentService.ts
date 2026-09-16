import { http } from "@/lib/http";
import type { ApiResponse, UploadDocumentData, UploadDocumentRequest } from "@/types/api";

export async function uploadDocument(payload: UploadDocumentRequest) {
  const response = await http.post<ApiResponse<UploadDocumentData>>(
    "/api/v1/documents/upload",
    payload,
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}

export async function uploadDocumentFile(formData: FormData) {
  const response = await http.post<ApiResponse<UploadDocumentData>>(
    "/api/v1/documents/upload",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}

export async function deleteDocument(documentId: string) {
  const response = await http.delete<ApiResponse<null>>(`/api/v1/documents/${documentId}`);
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
}

export async function reindexDocument(documentId: string) {
  const response = await http.post<ApiResponse<UploadDocumentData>>(
    `/api/v1/documents/${documentId}/reindex`,
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}
