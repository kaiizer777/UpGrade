import { z } from "zod";

const envSchema = z.object({
  NEXT_PUBLIC_API_BASE_URL: z
    .string()
    .url()
    .default("http://127.0.0.1:8000"),
});

const rawUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

const parsedEnv = envSchema.safeParse({
  NEXT_PUBLIC_API_BASE_URL:
    rawUrl && rawUrl.trim() !== "" ? rawUrl : "http://127.0.0.1:8000",
});

export const env = parsedEnv.success
  ? parsedEnv.data
  : {
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000",
    };

export const API_BASE_URL = env.NEXT_PUBLIC_API_BASE_URL.replace(/\/+$/, "");
