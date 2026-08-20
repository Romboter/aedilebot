// Operator allowlist for commands whose replies are private to the operator.
// User-only (no guild check), unlike /admin_swap's stricter user+guild rule.
const SNOWFLAKE = /^\d{17,20}$/;

export function isOperator(userId: string, env: NodeJS.ProcessEnv = process.env): boolean {
  const owners = (env.ADMIN_USER_IDS ?? "").split(/[\s,;]+/).filter((id) => SNOWFLAKE.test(id));
  return SNOWFLAKE.test(userId) && owners.includes(userId);
}
