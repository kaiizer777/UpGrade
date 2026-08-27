/**
 * TypeScript types mirroring FastAPI schemas & SQLModel models.
 */

export type PacePreference = "chill" | "steady" | "intense";

export type SubjectProfileStatus = "onboarding" | "ready";

export type TopicStatus = "pending" | "active" | "done";

export type ChatRole = "user" | "assistant";

export interface Subject {
  id: string;
  title: string;
  description: string | null;
  created_at: string;
}

export interface SubjectCreate {
  title: string;
  description?: string | null;
}

export interface SubjectListItem {
  id: string;
  title: string;
  description: string | null;
  created_at: string;
  onboarding_status: string;
}

export interface CompletenessRead {
  score: number;
  filled_slots: string[];
  missing_slots: string[];
}

export interface SubjectProfileSlotRead {
  goal: string;
  current_level: string;
  background: string;
  motivation: string;
  pace_preference: PacePreference;
  status: SubjectProfileStatus;
}

export interface OnboardingAnswerRead {
  question: string;
  answer: string;
  created_at: string;
}

export interface OnboardingMessageRead {
  reply: string;
  status: string;
  questions_asked: number;
  max_questions: number;
  completeness: CompletenessRead;
  profile: SubjectProfileSlotRead | null;
}

export interface OnboardingStateRead {
  subject_id: string;
  status: string;
  questions_asked: number;
  max_questions: number;
  completeness: CompletenessRead;
  answers: OnboardingAnswerRead[];
  profile: SubjectProfileSlotRead | null;
}

export interface RoadmapTopicRead {
  id: number;
  title: string;
  order_index: number;
  prerequisite_ids: number[];
  status: TopicStatus;
}

export interface RoadmapRead {
  subject_id: string;
  topics: RoadmapTopicRead[];
  active_topic_id: number | null;
}

export interface FeedPostRead {
  id: number;
  topic_id: number;
  content: string;
  order_index: number;
  created_at: string;
}

export interface FeedTopicSummary {
  id: number;
  title: string;
  order_index: number;
  status: string;
  prerequisite_ids: number[];
}

export interface FeedResponse {
  subject_id: string;
  topic: FeedTopicSummary | null;
  topic_id: number | null;
  posts: FeedPostRead[];
  post_count: number;
  all_topics_completed?: boolean;
}

export interface PrefetchResponse {
  topic_id: number;
  status: string;
  post_count: number;
}

export interface TopicCompleteResponse {
  completed_topic_id: number;
  status: string;
  deleted_feed_posts_count: number;
  next_topic_id: number | null;
  next_topic_title?: string | null;
  all_topics_completed: boolean;
}

export interface ChatMessageRead {
  id: number;
  topic_id: number;
  role: ChatRole | string;
  content: string;
  created_at?: string | null;
}

export interface ChatTurnResponse {
  reply: string;
  messages: ChatMessageRead[];
}

export interface ChatHistoryResponse {
  messages: ChatMessageRead[];
  topic_id: number;
  subject_id: string;
}
