import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toQuery } from "./client";
import type {
  AgendaItem,
  BillsPage,
  Compare,
  CompareVote,
  Expenses,
  FeedItem,
  FeedType,
  Follow,
  FollowPrefs,
  House,
  NewsItem,
  Page,
  PoliticianProfile,
  PoliticianSummary,
  PoliticianVote,
  Stats,
  User,
  VoteDetail,
} from "./types";

function infinite<T>(key: unknown[], path: (cursor?: string) => string, enabled = true) {
  return {
    queryKey: key,
    queryFn: ({ pageParam }: { pageParam?: string }) => api<Page<T>>(path(pageParam)),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: Page<T>) => last.next_cursor ?? undefined,
    enabled,
  };
}

export const useMe = (enabled: boolean) =>
  useQuery({ queryKey: ["me"], queryFn: () => api<User>("/me"), enabled, retry: false });

export interface SearchFilters {
  q?: string;
  uf?: string;
  party?: string;
  house?: House | "";
}

export const useSearch = (f: SearchFilters) =>
  useInfiniteQuery(
    infinite<PoliticianSummary>(["search", f], (cursor) => `/politicians${toQuery({ ...f, cursor })}`),
  );

export const usePolitician = (slug: string) =>
  useQuery({
    queryKey: ["politician", slug],
    queryFn: () => api<PoliticianProfile>(`/politicians/${slug}`),
    enabled: !!slug,
  });

export const useStats = (slug: string, period?: string) =>
  useQuery({
    queryKey: ["stats", slug, period],
    queryFn: () => api<Stats>(`/politicians/${slug}/stats${toQuery({ period })}`),
  });

export const useAgenda = (slug: string) =>
  useQuery({ queryKey: ["agenda", slug], queryFn: () => api<AgendaItem[]>(`/politicians/${slug}/agenda`) });

export const usePoliticianVotes = (slug: string) =>
  useInfiniteQuery(
    infinite<PoliticianVote>(["pvotes", slug], (cursor) => `/politicians/${slug}/votes${toQuery({ cursor })}`),
  );

export const usePoliticianNews = (slug: string) =>
  useInfiniteQuery(
    infinite<NewsItem>(["pnews", slug], (cursor) => `/politicians/${slug}/news${toQuery({ cursor })}`),
  );

export const usePoliticianBills = (slug: string, type: string, q: string) =>
  useInfiniteQuery({
    queryKey: ["pbills", slug, type, q],
    queryFn: ({ pageParam }: { pageParam?: string }) =>
      api<BillsPage>(`/politicians/${slug}/bills${toQuery({ type, q, cursor: pageParam })}`),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: BillsPage) => last.next_cursor ?? undefined,
  });

export const useExpenses = (slug: string, year: number) =>
  useQuery({
    queryKey: ["expenses", slug, year],
    queryFn: () => api<Expenses>(`/politicians/${slug}/expenses${toQuery({ year })}`),
  });

export const useVote = (id: string) =>
  useQuery({ queryKey: ["vote", id], queryFn: () => api<VoteDetail>(`/votes/${id}`) });

export const useFollows = (enabled = true) =>
  useQuery({ queryKey: ["follows"], queryFn: () => api<Follow[]>("/me/follows"), enabled });

export const useFeed = (type: FeedType | "", enabled: boolean) =>
  useInfiniteQuery(
    infinite<FeedItem>(["feed", type], (cursor) => `/me/feed${toQuery({ type, cursor })}`, enabled),
  );

export const useNews = (politician: string, enabled: boolean) =>
  useInfiniteQuery(
    infinite<NewsItem>(["news", politician], (cursor) => `/news${toQuery({ politician, cursor })}`, enabled),
  );

export const useCompare = (a: string, b: string, period?: string) =>
  useQuery({
    queryKey: ["compare", a, b, period],
    queryFn: () => api<Compare>(`/compare${toQuery({ a, b, period })}`),
    enabled: !!a && !!b && a !== b,
  });

export const useCompareVotes = (a: string, b: string, period: string | undefined, divergent: boolean) =>
  useInfiniteQuery(
    infinite<CompareVote>(
      ["compare-votes", a, b, period, divergent],
      (cursor) => `/compare/votes${toQuery({ a, b, period, divergent: divergent || undefined, cursor })}`,
      !!a && !!b && a !== b,
    ),
  );

export const useDataStatus = () =>
  useQuery({
    queryKey: ["status"],
    queryFn: () => api<{ jobs: Record<string, string | null> }>("/status"),
    staleTime: 10 * 60_000,
  });

export function useFollowMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, follow, prefs }: { id: string; follow: boolean; prefs?: FollowPrefs }) =>
      follow
        ? api(`/me/follows/${id}`, { method: "PUT", body: JSON.stringify(prefs ?? {}) })
        : api(`/me/follows/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["follows"] });
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: ["news"] });
      qc.invalidateQueries({ queryKey: ["politician"] });
    },
  });
}
