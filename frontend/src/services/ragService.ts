import { http } from "@/lib/http";
import type {
  ApiResponse,
  FeedbackData,
  FeedbackRequest,
  RetrieveData,
  RetrieveRequest,
} from "@/types/api";

export async function retrieve(payload: RetrieveRequest) {
  const response = await http.post<ApiResponse<RetrieveData>>(
    "/api/v1/rag/retrieve",
    payload,
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}

export async function submitFeedback(payload: FeedbackRequest) {
  const response = await http.post<ApiResponse<FeedbackData>>(
    "/api/v1/rag/feedback",
    payload,
  );
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}
