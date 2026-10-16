// Mirrors the backend response schemas (backend/app/schemas). There is no
// ground truth field anywhere in the client: the API never sends it.

export type VoteValue = "AI" | "REAL";
export type ReactionKind = "heart" | "like" | "laugh";
export type RankKey = "bronze" | "silver" | "gold" | "platinum" | "palladium";

export interface UserSummary {
  id: number;
  handle: string;
  display_name: string;
  avatar_id: number;
  rank: RankKey;
}

export interface Rank {
  key: RankKey;
  name: string;
  min_xp: number;
}

export interface Profile {
  id: number;
  handle: string;
  display_name: string;
  avatar_id: number;
  xp: number;
  rank: Rank;
  next_rank: Rank | null;
  progress: number;
}

/** Returned by login and by the "am I signed in?" check. */
export interface SessionInfo {
  user: Profile;
  blind_mode: boolean;
  csrf_token: string;
}

export interface Media {
  kind: "image" | "video";
  url: string;
  mime_type: string;
  width: number | null;
  height: number | null;
}

export interface VoteCounts {
  ai: number;
  real: number;
}

export interface ReactionCounts {
  heart: number;
  like: number;
  laugh: number;
}

export interface Post {
  id: number;
  author: UserSummary;
  caption: string | null;
  media: Media;
  // null while Blind Mode hides them (blind === true): the server never sent them.
  votes: VoteCounts | null;
  reactions: ReactionCounts | null;
  my_vote: VoteValue | null;
  my_reaction: ReactionKind | null;
  comment_count: number | null;
  blind: boolean;
  created_at: string;
}

export interface Comment {
  id: number;
  post_id: number;
  author: UserSummary;
  body: string;
  created_at: string;
  mine: boolean;
}

export interface CommentList {
  items: Comment[];
}

export interface LeaderboardEntry {
  position: number;
  user: UserSummary;
  xp: number;
  rank_name: string;
}

export interface Leaderboard {
  items: LeaderboardEntry[];
}

export interface ScanSignal {
  detector: string;
  label: string;
  status: "ok" | "no_signal" | "unavailable" | "error";
  score: number | null;
  conclusive: boolean;
  weight: number;
  explanation: string;
}

export interface ScanResult {
  media_kind: "image" | "video";
  verdict: "likely_ai" | "likely_real" | "inconclusive";
  verdict_label: string;
  /** 0..100, or null when the verdict is inconclusive. */
  score: number | null;
  signals: ScanSignal[];
  notice: string;
}

export interface FeedPage {
  items: Post[];
  next_cursor: string | null;
}

export interface VoteState {
  post_id: number;
  my_vote: VoteValue | null;
  votes: VoteCounts | null;
  me: { xp: number; rank: RankKey };
}

export interface ReactionState {
  post_id: number;
  my_reaction: ReactionKind | null;
  reactions: ReactionCounts;
}

export interface ActivityItem {
  type: "voted" | "posted";
  at: string;
  post: Post;
  vote: VoteValue | null;
}

export interface Activity {
  items: ActivityItem[];
}
