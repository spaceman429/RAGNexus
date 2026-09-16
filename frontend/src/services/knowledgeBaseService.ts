import { http } from "@/lib/http";
import type {
  ApiResponse,
  CreateKnowledgeBaseRequest,
  KnowledgeBaseData,
  KnowledgeBaseDetailData,
  TenantTreeItem,
  UpdateKnowledgeBaseRequest,
} from "@/types/api";

export async function createKnowledgeBase(payload: CreateKnowledgeBaseRequest) {
  const response = await http.post<ApiResponse<KnowledgeBaseData>>(
    "/api/v1/knowledge-bases/create",
    payload,
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}

export async function fetchTree(keyword?: string) {
  const response = await http.get<ApiResponse<TenantTreeItem[]>>(
    "/api/v1/knowledge-bases/tree",
    { params: keyword ? { keyword } : undefined },
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}

export async function fetchDetail(kbId: string) {
  const response = await http.get<ApiResponse<KnowledgeBaseDetailData>>(
    `/api/v1/knowledge-bases/${kbId}`,
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}

export async function updateKnowledgeBase(kbId: string, payload: UpdateKnowledgeBaseRequest) {
  const response = await http.patch<ApiResponse<KnowledgeBaseDetailData>>(
    `/api/v1/knowledge-bases/${kbId}`,
    payload,
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}

export async function deleteKnowledgeBase(kbId: string) {
  const response = await http.delete<ApiResponse<null>>(`/api/v1/knowledge-bases/${kbId}`);
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
}
