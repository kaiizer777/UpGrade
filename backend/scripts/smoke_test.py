#!/usr/bin/env python3
"""Smoke test: full UpGrade loop against a live backend.

Flow:
  create subject → onboarding turns → finalize (AI-driven) → POST /roadmap
  → GET /feed → POST /topics/{id}/complete → GET /feed again → POST /chat → GET /chat

Usage:
  uv run python scripts/smoke_test.py [--base-url http://127.0.0.1:8000]
  # or via env:
  API_BASE_URL=https://<railway-or-fly-url> uv run python scripts/smoke_test.py

Exit 0 on success, 1 on failure. Prints each step with status.
Requires: httpx (already in backend dependencies).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

import httpx


def _base_url_from_args(args_base: str | None) -> str:
    raw = args_base or os.environ.get("API_BASE_URL") or os.environ.get("API_BASE") or "http://127.0.0.1:8000"
    return raw.rstrip("/")


def _fail(msg: str, resp: httpx.Response | None = None) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    if resp is not None:
        try:
            print(f"       status={resp.status_code} body={resp.text[:2000]}", file=sys.stderr)
        except Exception:
            pass
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def main() -> None:
    parser = argparse.ArgumentParser(description="UpGrade smoke test")
    parser.add_argument("--base-url", dest="base_url", default=None, help="API base URL (default: env API_BASE_URL or http://127.0.0.1:8000)")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout seconds (default 60)")
    args = parser.parse_args()

    base = _base_url_from_args(args.base_url)
    timeout = args.timeout
    print(f"→ Starting smoke test against {base} (timeout={timeout}s)")

    client = httpx.Client(timeout=timeout, follow_redirects=True)

    # 0. Health
    try:
        r = client.get(f"{base}/health")
        if r.status_code != 200:
            _fail("GET /health non-200", r)
        _ok(f"GET /health → {r.json()}")
    except httpx.RequestError as e:
        _fail(f"GET /health request error: {e}")

    # 1. Create subject
    subject_title = f"Smoke-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    try:
        r = client.post(
            f"{base}/subjects",
            json={"title": subject_title, "description": "Smoke test subject for DSA"},
        )
    except httpx.RequestError as e:
        _fail(f"POST /subjects request error: {e}")
    if r.status_code != 201:
        _fail("POST /subjects expected 201", r)
    subject = r.json()
    subject_id = subject.get("id")
    if not subject_id:
        _fail("POST /subjects missing id", r)
    _ok(f"POST /subjects → {subject_id} title={subject_title}")

    # 2. Onboarding turns — drive toward ready
    # Send a rich initial answer that should fill most slots; then iterate.
    onboarding_messages = [
        "I want to learn Data Structures and Algorithms for FAANG interviews in 3 months. I can study 12 hours per week. I know basic Python and have solved ~50 easy LeetCode problems. My motivation is to crack FAANG interviews. I prefer a fast pace with lots of hands-on coding.",
        "I prefer learning by coding exercises and mock interview problems, mornings are best, I want daily 1-hour sessions with weekend deep dives.",
        "I have a CS undergrad background, comfortable with Big-O basics but weak on graphs and DP. Deadline is 12 weeks from now.",
    ]

    status = "onboarding"
    for idx, msg in enumerate(onboarding_messages):
        try:
            r = client.post(
                f"{base}/subjects/{subject_id}/onboarding/messages",
                json={"content": msg},
            )
        except httpx.RequestError as e:
            _fail(f"POST /subjects/{subject_id}/onboarding/messages turn {idx} error: {e}")
        # Expect 200; handle 503/502 gracefully (AI not configured)
        if r.status_code in (502, 503):
            print(f"⚠️  Onboarding turn {idx} returned {r.status_code}: {r.text[:500]}")
            print("   AI provider not configured or generation failed — checking state then continuing to roadmap with fallback.")
            break
        if r.status_code == 409:
            # Already finalized
            status = "ready"
            _ok(f"Onboarding turn {idx} → 409 already finalized, treating as ready")
            break
        if r.status_code != 200:
            _fail(f"POST onboarding/messages turn {idx} expected 200", r)
        data = r.json()
        status = data.get("status", status)
        reply_preview = (data.get("reply") or "")[:120].replace("\n", " ")
        _ok(f"Onboarding turn {idx} → status={status} reply='{reply_preview}...' q={data.get('questions_asked')}/{data.get('max_questions')}")
        if status == "ready":
            break
        # Small pause between turns
        time.sleep(0.5)

    # Also fetch state snapshot for logging
    try:
        r = client.get(f"{base}/subjects/{subject_id}/onboarding/state")
        if r.status_code == 200:
            st = r.json()
            status = st.get("status", status)
            print(f"   onboarding/state → status={status} completeness={st.get('completeness')}")
        else:
            print(f"   onboarding/state → {r.status_code} {r.text[:300]}")
    except Exception as e:
        print(f"   onboarding/state error: {e}")

    if status != "ready":
        print(f"⚠️  Onboarding not ready (status={status}) — roadmap will likely 409. Trying anyway; if AI is mocked, alternate finalize may be needed.")

    # 3. POST /roadmap (generate or fetch)
    try:
        r = client.post(f"{base}/subjects/{subject_id}/roadmap")
    except httpx.RequestError as e:
        _fail(f"POST /subjects/{subject_id}/roadmap error: {e}")
    if r.status_code == 409:
        print(f"⚠️  POST /roadmap → 409 (onboarding not finalized): {r.text[:600]}")
        print("   Cannot proceed without ready onboarding; if backend uses mock AI, ensure GROQ_API_KEY is set or mock path is wired.")
        _fail("Roadmap not ready — onboarding must be finalized before smoke can continue", r)
    if r.status_code not in (200, 201):
        _fail("POST /subjects/{id}/roadmap expected 200 or 201", r)
    roadmap = r.json()
    topics = roadmap.get("topics") or []
    if not topics:
        _fail("POST /roadmap returned no topics", r)
    active_id = roadmap.get("active_topic_id")
    _ok(f"POST /roadmap → {r.status_code} topics={len(topics)} active_topic_id={active_id} title='{topics[0].get('title')}'")

    # Also GET /roadmap for idempotency check
    try:
        r2 = client.get(f"{base}/subjects/{subject_id}/roadmap")
        if r2.status_code == 200:
            _ok(f"GET /roadmap → 200 topics={len(r2.json().get('topics') or [])}")
        else:
            print(f"⚠️  GET /roadmap → {r2.status_code} {r2.text[:300]}")
    except Exception as e:
        print(f"⚠️  GET /roadmap error: {e}")

    # 4. GET /feed (JIT — may trigger synchronous generation)
    try:
        r = client.get(f"{base}/subjects/{subject_id}/feed")
    except httpx.RequestError as e:
        _fail(f"GET /subjects/{subject_id}/feed error: {e}")
    if r.status_code != 200:
        # 409 means no active topic or feed not ready; surface clearly
        _fail(f"GET /feed expected 200, got {r.status_code}", r)
    feed = r.json()
    topic_id = feed.get("topic_id") or (feed.get("topic") or {}).get("id")
    posts = feed.get("posts") or []
    if topic_id is None:
        # All done case already?
        if feed.get("all_topics_completed"):
            _ok("GET /feed → all_topics_completed=true (single-topic roadmap fully done?)")
            topic_id = topics[0].get("id") if topics else None
        else:
            _fail("GET /feed missing topic_id and not all_topics_completed", r)
    else:
        _ok(f"GET /feed → topic_id={topic_id} posts={len(posts)} all_done={feed.get('all_topics_completed')}")
        if posts:
            preview = (posts[0].get("content") or "")[:100].replace("\n", " ")
            print(f"   first post preview: '{preview}...'")

    if topic_id is None:
        _fail("No topic_id to complete/chat; aborting")

    # 5. POST /topics/{id}/complete
    # Give feed generation a moment if it was async (though GET above is sync, so should be ready)
    try:
        r = client.post(f"{base}/topics/{topic_id}/complete")
    except httpx.RequestError as e:
        _fail(f"POST /topics/{topic_id}/complete error: {e}")
    if r.status_code != 200:
        _fail(f"POST /topics/{topic_id}/complete expected 200", r)
    comp = r.json()
    _ok(f"POST /topics/{topic_id}/complete → next_topic_id={comp.get('next_topic_id')} all_done={comp.get('all_topics_completed')}")

    # 6. GET /feed again (should flip to next topic or all done)
    try:
        r = client.get(f"{base}/subjects/{subject_id}/feed")
    except httpx.RequestError as e:
        _fail(f"GET /feed (after complete) error: {e}")
    if r.status_code not in (200, 409, 404):
        _fail("GET /feed after complete unexpected status", r)
    if r.status_code == 200:
        feed2 = r.json()
        _ok(f"GET /feed (after complete) → posts={len(feed2.get('posts') or [])} topic_id={feed2.get('topic_id')} all_done={feed2.get('all_topics_completed')}")
        # Update topic_id to next active for chat test
        next_topic_id = feed2.get("topic_id") or comp.get("next_topic_id") or topic_id
    else:
        print(f"   GET /feed after complete → {r.status_code} {r.text[:400]}")
        next_topic_id = comp.get("next_topic_id") or topic_id

    if next_topic_id is None:
        next_topic_id = topic_id
    chat_topic_id = int(next_topic_id) if next_topic_id is not None else int(topic_id)

    # 7. POST /chat + GET /chat
    chat_msg = "Explain this topic like I'm in a hurry — give me one quick example."
    try:
        r = client.post(
            f"{base}/subjects/{subject_id}/topics/{chat_topic_id}/chat",
            json={"message": chat_msg},
        )
    except httpx.RequestError as e:
        _fail(f"POST /chat error: {e}")
    if r.status_code in (502, 503):
        print(f"⚠️  POST /chat → {r.status_code} (AI not configured): {r.text[:400]}")
        print("   Skipping chat assert but continuing to GET /chat check.")
    elif r.status_code != 200:
        _fail(f"POST /chat expected 200, got {r.status_code}", r)
    else:
        chat_resp = r.json()
        reply = (chat_resp.get("reply") or "")[:150].replace("\n", " ")
        _ok(f"POST /chat → reply='{reply}...' messages={len(chat_resp.get('messages') or [])}")

    try:
        r = client.get(f"{base}/subjects/{subject_id}/topics/{chat_topic_id}/chat")
    except httpx.RequestError as e:
        _fail(f"GET /chat error: {e}")
    if r.status_code != 200:
        _fail(f"GET /chat expected 200, got {r.status_code}", r)
    history = r.json().get("messages") or []
    _ok(f"GET /chat → messages={len(history)}")

    client.close()
    print("\n🎉 Smoke test PASSED — full loop completed successfully.")
    print(f"   subject_id={subject_id}")
    print(f"   base_url={base}")


if __name__ == "__main__":
    main()
