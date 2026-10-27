import { api } from "./api";

export async function getLiveKitConnection() {
  return api.voiceToken();
}
