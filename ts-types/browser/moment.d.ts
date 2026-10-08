export interface MomentValue { isAfter(other: MomentValue): boolean }
export interface MomentRuntime { (value: string | undefined, format: string): MomentValue }
declare global { interface Window { moment: MomentRuntime } }
