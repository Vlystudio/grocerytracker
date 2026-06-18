// Shared TypeScript shapes mirroring the Supabase tables the website reads.

export type ResearchRecord = {
  id: string;
  source_id: string | null;
  topic_id: string | null;
  title: string;
  url: string;
  doi: string | null;
  authors: string[];
  publication_date: string | null;
  abstract: string | null;
  summary: string | null;
  study_type: string | null;
  sample_size: number | null;
  key_findings: string[];
  pdf_links: string[];
  source_website: string;
  retrieved_at: string;
  extraction_engine: string | null;
  created_at: string;
};

export type ExtractedTable = {
  id: string;
  record_id: string;
  table_index: number;
  caption: string | null;
  data: { headers?: string[]; rows?: string[][] };
};

export type ResearchTopic = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
};

export type ResearchSource = {
  id: string;
  name: string;
  base_url: string;
  allowed_domains: string[];
  search_keywords: string[];
  crawl_depth: number;
  rate_limit: number;
  max_pages: number;
  engine: "scrapy" | "playwright";
  enabled: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ScrapeRun = {
  id: string;
  source_id: string | null;
  trigger: "manual" | "scheduled";
  status: "queued" | "running" | "success" | "partial" | "failed";
  started_at: string | null;
  finished_at: string | null;
  pages_crawled: number;
  records_found: number;
  records_new: number;
  errors_count: number;
  notes: string | null;
  created_at: string;
};

export type GroceryDeal = {
  id: string;
  flipp_item_id: number | null;
  store: string;
  merchant_raw: string | null;
  product_name: string;
  brand: string | null;
  price: number | null;
  discount: string | null;
  valid_from: string | null;
  valid_to: string | null;
  image_url: string | null;
  flyer_id: number | null;
  postal_code: string | null;
  retrieved_at: string;
  created_at: string;
};

export type GroceryStore = {
  id: string;
  display_name: string;
  match_key: string;
  enabled: boolean;
};

export type GroceryLocation = {
  id: string;
  name: string;
  postal_code: string;
  enabled: boolean;
};

export type ScrapeError = {
  id: string;
  run_id: string | null;
  source_id: string | null;
  url: string | null;
  error_type: string | null;
  message: string | null;
  resolved: boolean;
  occurred_at: string;
};
