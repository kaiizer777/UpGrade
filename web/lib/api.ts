import { z } from "zod";
import { API_BASE_URL } from "@/lib/config";
import type {
  ChatHistoryResponse,
  ChatTurnResponse,
  FeedResponse,
  OnboardingMessageRead,
  OnboardingStateRead,
  PrefetchResponse,
  RoadmapRead,
  Subject,
  SubjectCreate,
  SubjectListItem,
  TopicCompleteResponse,
} from "@/lib/types";

// ==========================================
// Zod DTO Schemas
// ==========================================

export const SubjectSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  description: z.string().nullable().optional().default(null),
  created_at: z.string(),
});

export const SubjectCreateSchema = z.object({
  title: z.string().min(1),
  description: z.string().nullable().optional(),
});

export const SubjectListItemSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  description: z.string().nullable().optional().default(null),
  created_at: z.string(),
  onboarding_status: z.string(),
});

export const CompletenessReadSchema = z.object({
  score: z.number(),
  filled_slots: z.array(z.string()),
  missing_slots: z.array(z.string()),
});

export const SubjectProfileSlotReadSchema = z.object({
  goal: z.string(),
  current_level: z.string(),
  background: z.string(),
  motivation: z.string(),
  pace_preference: z.enum(["chill", "steady", "intense"]),
  status: z.enum(["onboarding", "ready"]),
});

export const OnboardingAnswerReadSchema = z.object({
  question: z.string(),
  answer: z.string(),
  created_at: z.string(),
});

export const OnboardingMessageReadSchema = z.object({
  reply: z.string(),
  status: z.string(),
  questions_asked: z.number(),
  max_questions: z.number(),
  completeness: CompletenessReadSchema,
  profile: SubjectProfileSlotReadSchema.nullable().optional().default(null),
});

export const OnboardingStateReadSchema = z.object({
  subject_id: z.string().uuid(),
  status: z.string(),
  questions_asked: z.number(),
  max_questions: z.number(),
  completeness: CompletenessReadSchema,
  answers: z.array(OnboardingAnswerReadSchema),
  profile: SubjectProfileSlotReadSchema.nullable().optional().default(null),
});

export const RoadmapTopicReadSchema = z.object({
  id: z.number(),
  title: z.string(),
  order_index: z.number(),
  prerequisite_ids: z.array(z.number()),
  status: z.enum(["pending", "active", "done"]),
});

export const RoadmapReadSchema = z.object({
  subject_id: z.string().uuid(),
  topics: z.array(RoadmapTopicReadSchema),
  active_topic_id: z.number().nullable().optional().default(null),
});

export const FeedPostReadSchema = z.object({
  id: z.number(),
  topic_id: z.number(),
  content: z.string(),
  order_index: z.number(),
  created_at: z.string(),
});

export const FeedTopicSummarySchema = z.object({
  id: z.number(),
  title: z.string(),
  order_index: z.number(),
  status: z.string(),
  prerequisite_ids: z.array(z.number()),
});

export const FeedResponseSchema = z.object({
  subject_id: z.string(),
  topic: FeedTopicSummarySchema.nullable().optional().default(null),
  topic_id: z.number().nullable().optional().default(null),
  posts: z.array(FeedPostReadSchema),
  post_count: z.number(),
  all_topics_completed: z.boolean().optional(),
});

export const PrefetchResponseSchema = z.object({
  topic_id: z.number(),
  status: z.string(),
  post_count: z.number(),
});

export const TopicCompleteResponseSchema = z.object({
  completed_topic_id: z.number(),
  status: z.string(),
  deleted_feed_posts_count: z.number(),
  next_topic_id: z.number().nullable().optional().default(null),
  next_topic_title: z.string().nullable().optional().default(null),
  all_topics_completed: z.boolean(),
});

export const ChatMessageReadSchema = z.object({
  id: z.number(),
  topic_id: z.number(),
  role: z.string(),
  content: z.string(),
  created_at: z.string().nullable().optional().default(null),
});

export const ChatTurnResponseSchema = z.object({
  reply: z.string(),
  messages: z.array(ChatMessageReadSchema),
});

export const ChatHistoryResponseSchema = z.object({
  messages: z.array(ChatMessageReadSchema),
  topic_id: z.number(),
  subject_id: z.string(),
});

// ==========================================
// Custom API Error Class
// ==========================================

export class ApiError extends Error {
  public status: number;
  public detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// ==========================================
// Base Fetcher
// ==========================================

async function request<T>(
  path: string,
  options: RequestInit = {},
  schema?: z.ZodType<T>
): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(options.headers);

  if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail: unknown = null;
    let errorMessage = `API request failed with status ${response.status}`;
    try {
      const data = await response.json();
      errorDetail = data;
      if (data && typeof data === "object" && "detail" in data) {
        errorMessage = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      try {
        const text = await response.text();
        if (text) errorMessage = text;
      } catch {
        // use default message
      }
    }
    throw new ApiError(response.status, errorMessage, errorDetail);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null as unknown as T;
  }

  const json = await response.json();

  if (schema) {
    return schema.parse(json);
  }

  return json as T;
}

// ==========================================
// Typed API Endpoints (Direct FastAPI Calls)
// ==========================================

/**
 * Fetch all subjects with their onboarding status.
 */
export async function getSubjects(): Promise<SubjectListItem[]> {
  return request<SubjectListItem[]>(
    "/subjects",
    { method: "GET" },
    z.array(SubjectListItemSchema)
  );
}

/**
 * Create a new learning subject.
 */
export async function createSubject(payload: SubjectCreate): Promise<Subject> {
  SubjectCreateSchema.parse(payload);
  return request<Subject>(
    "/subjects",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    SubjectSchema
  );
}

/**
 * Get a single subject by ID (fetches from subject list or onboarding state).
 */
export async function getSubject(subjectId: string): Promise<SubjectListItem | null> {
  const subjects = await getSubjects();
  return subjects.find((s) => s.id === subjectId) ?? null;
}

/**
 * Post an onboarding conversational turn.
 */
export async function postOnboardingMessage(
  subjectId: string,
  content: string
): Promise<OnboardingMessageRead> {
  return request<OnboardingMessageRead>(
    `/subjects/${encodeURIComponent(subjectId)}/onboarding/messages`,
    {
      method: "POST",
      body: JSON.stringify({ content }),
    },
    OnboardingMessageReadSchema
  );
}

/**
 * Get the current onboarding state for a subject.
 */
export async function getOnboardingState(subjectId: string): Promise<OnboardingStateRead> {
  return request<OnboardingStateRead>(
    `/subjects/${encodeURIComponent(subjectId)}/onboarding/state`,
    { method: "GET" },
    OnboardingStateReadSchema
  );
}

/**
 * Get existing roadmap for a subject.
 */
export async function getRoadmap(subjectId: string): Promise<RoadmapRead> {
  return request<RoadmapRead>(
    `/subjects/${encodeURIComponent(subjectId)}/roadmap`,
    { method: "GET" },
    RoadmapReadSchema
  );
}

/**
 * Generate or fetch roadmap for a subject (idempotent POST).
 */
export async function createRoadmap(subjectId: string): Promise<RoadmapRead> {
  return request<RoadmapRead>(
    `/subjects/${encodeURIComponent(subjectId)}/roadmap`,
    { method: "POST" },
    RoadmapReadSchema
  );
}

/**
 * Get JIT feed for active topic or specific topic.
 */
export async function getFeed(
  subjectId: string,
  topicId?: number
): Promise<FeedResponse> {
  const query = topicId !== undefined ? `?topic_id=${encodeURIComponent(topicId)}` : "";
  return request<FeedResponse>(
    `/subjects/${encodeURIComponent(subjectId)}/feed${query}`,
    { method: "GET" },
    FeedResponseSchema
  );
}

/**
 * Complete the active topic, activate next topic, and trigger next feed.
 */
export async function completeTopic(topicId: number): Promise<TopicCompleteResponse> {
  return request<TopicCompleteResponse>(
    `/topics/${encodeURIComponent(topicId)}/complete`,
    { method: "POST" },
    TopicCompleteResponseSchema
  );
}

/**
 * Trigger prefetch generation for a topic.
 */
export async function prefetchTopic(
  subjectId: string,
  topicId: number
): Promise<PrefetchResponse> {
  return request<PrefetchResponse>(
    `/subjects/${encodeURIComponent(subjectId)}/topics/${encodeURIComponent(topicId)}/prefetch`,
    { method: "POST" },
    PrefetchResponseSchema
  );
}

/**
 * Get chat history for a specific topic.
 */
export async function getChat(
  subjectId: string,
  topicId: number
): Promise<ChatHistoryResponse> {
  return request<ChatHistoryResponse>(
    `/subjects/${encodeURIComponent(subjectId)}/topics/${encodeURIComponent(topicId)}/chat`,
    { method: "GET" },
    ChatHistoryResponseSchema
  );
}

/**
 * Send an open chat question scoped to topic and subject.
 */
export async function postChat(
  subjectId: string,
  topicId: number,
  message: string
): Promise<ChatTurnResponse> {
  return request<ChatTurnResponse>(
    `/subjects/${encodeURIComponent(subjectId)}/topics/${encodeURIComponent(topicId)}/chat`,
    {
      method: "POST",
      body: JSON.stringify({ message }),
    },
    ChatTurnResponseSchema
  );
}
