"use client";

import * as React from "react";
import { ChatSheet, type ChatSheetProps } from "@/components/chat-sheet";

export type FeedChatSheetProps = ChatSheetProps;

/**
 * @deprecated Use `ChatSheet` from `@/components/chat-sheet` instead.
 */
export function FeedChatSheet(props: FeedChatSheetProps) {
  return <ChatSheet {...props} />;
}
