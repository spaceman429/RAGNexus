/** 清理 chunk 中残留的 docx 书签/HTML 标签，避免 Markdown 渲染成可见文本。 */
export function sanitizeChunkMarkdown(content: string): string {
  return content
    .replace(/<a\s+id="[^"]*"\s*><\/a>\s*/gi, "")
    .replace(/<br\s*\/?>/gi, "\n");
}
