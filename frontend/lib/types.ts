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
  votes: VoteCounts;
  reactions: ReactionCounts;
  my_vote: VoteValue | null;
  my_reaction: ReactionKind | null;
  created_at: string;
}

export interface FeedPage {
  items: Post[];
  next_cursor: string | null;
}

export interface VoteState {
  post_id: number;
  my_vote: VoteValue | null;
  votes: VoteCounts;
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
