// Formatting shared by every page. Dates from the API are plain ISO days (YYYY-MM-DD) in store time.

const asDate = (iso: string) => new Date(iso.length === 10 ? `${iso}T12:00:00` : iso)

/** "Wed 4 Nov" */
export const shortDay = (iso: string) =>
  asDate(iso).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

/** "Monday 2 November" */
export const longDay = (iso: string) =>
  asDate(iso).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

/** "storage_capacity" → "storage capacity" */
export const humanize = (code: string) => code.replaceAll('_', ' ')

/** "modify" → "Modify" */
export const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** What each agent tool looks at, in a buyer's words (used by the trace and the evidence chips). */
export const TOOL_WORDS: Record<string, string> = {
  get_situation: 'the situation', get_sku_profile: 'product details', get_inventory: 'stock on hand',
  get_open_pos: 'orders already on the way', get_sales_history: 'sales history', get_forecast: 'the forecast',
  get_promotions: 'promotions', get_supplier_terms: 'supplier terms', get_supplier_performance: 'supplier reliability',
  get_budget: 'the budget', get_storage_status: 'storage space', get_other_nodes_stock: 'other stores’ stock',
  check_data_quality: 'data quality', analyze_demand: 'demand vs forecast', compute_requirement: 'the real need',
  project_inventory: 'a stock projection', generate_options: 'the buying options', validate_plan: 'a rule check (dry run)',
}
