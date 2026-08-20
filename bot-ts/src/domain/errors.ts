// Single home for all domain errors — ported from the exception classes that
// were scattered across bot.py (EntityNotFoundError and its subclasses) and
// used bare `ZeroDivisionError` (calculator.py's calculate_damage). Consumers
// throughout domain/* import from here instead of a discord-aware module, per
// the plan's dependency direction (gateway -> commands -> domain -> data).

export class EntityNotFoundError extends Error {
  readonly entityName: string;

  constructor(
    entityName: string,
    message = "The requested entity was not found. Please try again.",
  ) {
    super(message);
    this.name = "EntityNotFoundError";
    this.entityName = entityName;
  }
}

export class InvalidTypeError extends EntityNotFoundError {
  constructor(
    entityName: string,
    message = "The entity was invalid for this operation. Please try again.",
  ) {
    super(entityName, message);
    this.name = "InvalidTypeError";
  }
}

export class TargetNotFoundError extends EntityNotFoundError {
  constructor(
    entityName: string,
    message = "The detected target is not found in my data set. Please try again.",
  ) {
    super(entityName, message);
    this.name = "TargetNotFoundError";
  }
}

export class TargetOfTypeNotFoundError extends EntityNotFoundError {
  constructor(
    entityName: string,
    message = "The detected target for this operation is not found in my data set. Please try again.",
  ) {
    super(entityName, message);
    this.name = "TargetOfTypeNotFoundError";
  }
}

export class WeaponNotFoundError extends EntityNotFoundError {
  constructor(
    entityName: string,
    message = "The detected weapon is not found in my data set. Please try again.",
  ) {
    super(entityName, message);
    this.name = "WeaponNotFoundError";
  }
}

export class LocationNotFoundError extends EntityNotFoundError {
  constructor(
    entityName: string,
    message = "I could not process a request because the town/relic was not found. Please try again.",
  ) {
    super(entityName, message);
    this.name = "LocationNotFoundError";
  }
}

export class BunkerSpecParseError extends TargetNotFoundError {
  constructor(
    entityName: string,
    message = "Invalid bunker specification, please try again with this example format: \n" +
      "`how many <weapon> to kill size <number> tier <1/2/3> bunker with <numer> <modification> ...`\n" +
      "Ex: `How many tremola to kill a size 15 t3 bunker with 2 mg 3 atg 3 howi 1 ramp`",
  ) {
    super(entityName, message);
    this.name = "BunkerSpecParseError";
  }
}

// Ported from calculator.py raising a bare ZeroDivisionError with a formatted
// message when real_damage rounds to 0 (100% mitigation for that damage/
// target-mitigation pair) — bot.py's error handler matched on the substring
// "does no damage to this entity" in the message, so the wording is preserved
// exactly for parity rather than reworded.
export class NoDamageError extends Error {
  readonly weaponName: string;
  readonly targetName: string;

  constructor(weaponName: string, targetName: string) {
    super(`This weapon (${weaponName}) does no damage to this entity (${targetName}).`);
    this.name = "NoDamageError";
    this.weaponName = weaponName;
    this.targetName = targetName;
  }
}
