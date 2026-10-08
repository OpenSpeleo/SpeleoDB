import type { Mock } from 'vitest';

/** Hoisted module doubles contain vi.fn properties, not receiver-dependent methods. */
export type ModuleMock<T> = {
    [Key in keyof T]: T[Key] extends (...args: infer Args) => infer Result
        ? Mock<(...args: Args) => Result>
        : T[Key];
};
