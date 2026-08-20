// Port of calculator.py's DamageCalculator.multitier_damage_calculator.
//
// The Python original has an `if self.damage_type == "BPDemolitionDamageType"`
// branch that is DEAD CODE: self.damage_type is always the dict copied from
// parse.damages[...], never the bare string, so that comparison is always
// False and the branch never executes. Not replicated here — only the
// always-taken 3-tier path is ported. Do not "fix" this into working code; it
// would change behavior for a case the original bot never actually took.
function calculateHitsToReachHealth(health: number, damage: number): number {
  return Math.ceil(health / damage);
}

export function multitierDamageCalculator(
  health: number,
  calculateDamage: (mitigationType: string) => number,
): string {
  const t = [
    calculateHitsToReachHealth(health, calculateDamage("Tier1GarrisonHouse")),
    calculateHitsToReachHealth(health, calculateDamage("Tier2GarrisonHouse")),
    calculateHitsToReachHealth(health, calculateDamage("Tier3GarrisonHouse")),
  ];
  return `${t[0]} (Tier 1) ${t[1]} (Tier 2) ${t[2]} (Tier 3)`;
}
