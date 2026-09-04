import api from "./client";

export interface SignupPayload {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

export async function signup(payload: SignupPayload) {
  const { data } = await api.post("/auth/signup/", payload);
  return data;
}

export async function login(email: string, password: string) {
  const { data } = await api.post("/auth/login/", { email, password });
  return data;
}

export async function me() {
  const { data } = await api.get("/auth/me/");
  return data;
}
