import type ts from 'typescript';
export interface DependencyGroups {
    dependencies?: Record<string, string>;
    devDependencies?: Record<string, string>;
    optionalDependencies?: Record<string, string>;
}
export interface PackageManifest extends DependencyGroups {
    name: string;
    packageManager: string;
    engines: { bun: string };
    trustedDependencies: string[];
    scripts?: Record<string, string>;
}
export interface BunLock {
    workspaces: { '': DependencyGroups };
    packages: Record<string, [string, string, { bundled?: boolean }, string?]>;
    trustedDependencies: string[];
}
export interface SetupBunStep { uses: string; with: { 'bun-version-file': string; 'bun-version'?: string } }
export interface RailpackRecipe { packages: { bun?: string }; steps: { build: { commands: { cmd: string }[] } } }
export interface CompilerConfiguration {
    extends?: string;
    files: string[];
    include: string[];
    references: { path: string }[];
    compilerOptions: ts.CompilerOptions & { types: string[]; lib: string[]; tsBuildInfoFile: string };
}
