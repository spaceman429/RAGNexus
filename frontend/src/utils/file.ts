export function getRelativePath(file: File) {
  return file.webkitRelativePath || file.name;
}

export interface IgnoredFile {
  relativePath: string;
  reason: string;
}

const SYSTEM_FILE_NAMES = new Set([".ds_store", "thumbs.db", "desktop.ini"]);
const SYSTEM_DIRECTORY_NAMES = new Set(["__macosx"]);

export function isHiddenOrSystemFile(file: File) {
  const relativePath = getRelativePath(file);
  const parts = relativePath.split(/[\\/]/).filter(Boolean);

  return parts.some((part) => {
    const normalized = part.toLowerCase();
    return part.startsWith(".") || SYSTEM_FILE_NAMES.has(normalized) || SYSTEM_DIRECTORY_NAMES.has(normalized);
  });
}

export function filterHiddenOrSystemFiles(files: File[]) {
  const accepted: File[] = [];
  const ignored: IgnoredFile[] = [];

  for (const file of files) {
    const relativePath = getRelativePath(file);
    if (isHiddenOrSystemFile(file)) {
      ignored.push({
        relativePath,
        reason: "隐藏或系统文件",
      });
      continue;
    }
    accepted.push(file);
  }

  return { accepted, ignored };
}

export function isSupportedTextFile(file: File) {
  const name = file.name.toLowerCase();
  return name.endsWith(".txt") || name.endsWith(".md");
}

export function isSupportedBinaryUploadFile(file: File) {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".docx");
}

export function isSupportedUploadFile(file: File) {
  return isSupportedTextFile(file) || isSupportedBinaryUploadFile(file);
}

export function readFileAsText(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("文件读取失败"));
    reader.readAsText(file);
  });
}
