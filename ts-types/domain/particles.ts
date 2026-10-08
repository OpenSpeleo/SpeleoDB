/** The existing error-page configuration accepted by the external tsParticles runtime. */
export interface ErrorParticlesConfiguration {
    fpsLimit: number;
    particles: {
        number: { value: number; density: { enable: boolean; area: number } };
        color: { value: string };
        shape: { type: string };
        opacity: {
            value: number;
            random: { enable: boolean; minimumValue: number };
            animation: { enable: boolean; speed: number; minimumValue: number; sync: boolean };
        };
        size: { value: number; random: { enable: boolean; minimumValue: number } };
        move: {
            enable: boolean;
            speed: number;
            direction: string;
            random: boolean;
            straight: boolean;
            outModes: { default: string };
        };
    };
    interactivity: { detectsOn: string; events: { resize: boolean } };
    detectRetina: boolean;
}

export interface ParticlesRuntime {
    load(targetId: string, configuration: ErrorParticlesConfiguration): Promise<unknown>;
}
