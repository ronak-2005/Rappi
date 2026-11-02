export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="error-box">{error}</div> : null
}
