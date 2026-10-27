// Espelha os schemas da API (backend/app/schemas). Documentação completa em /docs.

export type House = "camara" | "senado";
export type VoteChoice = "sim" | "nao" | "abstencao" | "obstrucao" | "ausente" | "art17";
export type FeedType = "vote" | "agenda" | "news" | "bill";

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface TokenOut {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface User {
  id: string;
  email: string;
  name: string;
  uf: string | null;
  role: string;
  auth_provider: string;
  created_at: string;
}

export interface PoliticianSummary {
  id: string;
  slug: string;
  house: House;
  name: string;
  party: string | null;
  uf: string;
  photo_url: string | null;
  in_office: boolean;
}

export interface PoliticianProfile extends PoliticianSummary {
  civil_name: string;
  email: string | null;
  social_links: string[];
  legislature: number | null;
  official_url: string;
  is_following: boolean;
  updated_at: string | null;
}

export interface Metric {
  value: number | null;
  house_avg: number | null;
}

export interface Stats {
  period: string;
  period_label: string;
  attendance_rate: Metric;
  sessions_total: number;
  sessions_present: number;
  sessions_justified: number;
  sessions_absent: number;
  votes_participated: Metric;
  votes_total: number;
  bills_authored: Metric;
  bills_reported: number;
  expenses_total: Metric;
  computed_at: string | null;
  methodology_url: string;
}

export interface AgendaItem {
  id: string;
  title: string;
  organ: string | null;
  location: string | null;
  starts_at: string;
  ends_at: string | null;
  status: string | null;
}

export interface Bill {
  id: string;
  type: string;
  number: number | null;
  year: number | null;
  official_summary: string | null;
  plain_summary: string | null;
  plain_summary_ai: boolean;
  url: string | null;
}

export interface VoteInfo {
  id: string;
  house: House;
  voted_at: string;
  description: string | null;
  result: string | null;
  yes_count: number;
  no_count: number;
  abstention_count: number;
  bill: Bill | null;
  source_url: string;
}

export interface PoliticianVote {
  vote: VoteInfo;
  choice: VoteChoice;
  party_orientation: string | null;
  with_party: boolean | null;
}

export interface VoteDetail extends VoteInfo {
  records: {
    politician: PoliticianSummary;
    choice: VoteChoice;
    party_orientation: string | null;
    is_followed: boolean;
  }[];
}

export interface NewsItem {
  id: string;
  url: string;
  title: string;
  snippet: string | null;
  source_name: string | null;
  published_at: string;
  image_url: string | null;
  politicians: PoliticianSummary[];
}

export interface Expenses {
  year: number;
  total: string;
  by_category: { category: string; total: string }[];
  by_month: { month: number; total: number }[];
}

export interface FollowPrefs {
  notify_votes: boolean;
  notify_agenda: boolean;
  notify_news: boolean;
}

export interface Follow extends FollowPrefs {
  politician: PoliticianSummary;
  created_at: string;
}

export interface FeedItem {
  id: number;
  type: FeedType;
  occurred_at: string;
  politician: PoliticianSummary;
  payload: Record<string, string | null>;
}
