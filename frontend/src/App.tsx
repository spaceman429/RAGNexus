import { Navigate, Route, Routes } from "react-router-dom";
import { KnowledgeFileTreePage } from "@/pages/KnowledgeFileTreePage";
import { KnowledgeUploadPage } from "@/pages/KnowledgeUploadPage";
import { RetrievePage } from "@/pages/RetrievePage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<KnowledgeUploadPage />} />
      <Route path="/knowledge-bases" element={<KnowledgeFileTreePage />} />
      <Route path="/retrieve" element={<RetrievePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

