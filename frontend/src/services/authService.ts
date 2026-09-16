import { http } from "@/lib/http";
import type { ApiResponse, AuthMeData } from "@/types/api";

export async function fetchAuthMe() {
  const response = await http.get<ApiResponse<AuthMeData>>("/api/v1/auth/me");
  if (response.data.code !== 0) {
    throw new Error(response.data.msg);
  }
  return response.data.data;
}
