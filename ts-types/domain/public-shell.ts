export interface ParticleOptions {
    quantity?: number | string | undefined;
    staticity?: number | string | undefined;
    ease?: number | string | undefined;
}

export interface ParticleCircle {
    x: number;
    y: number;
    translateX: number;
    translateY: number;
    size: number;
    alpha: number;
    targetAlpha: number;
    dx: number;
    dy: number;
    magnetism: number;
}

export interface AOSRuntime {
    init(options: { once: boolean; disable: string; duration: number; easing: string }): void;
}

export interface SwiperOptions {
    slidesPerView?: 'auto' | number;
    spaceBetween: number;
    centeredSlides: boolean;
    loop: boolean;
    speed?: number;
    noSwiping?: boolean;
    noSwipingClass?: string;
    autoplay?: { delay: number; disableOnInteraction: boolean };
    breakpoints?: { 320: { slidesPerView: number }; 640: { slidesPerView: number }; 1024: { slidesPerView: number } };
    grabCursor?: boolean;
    initialSlide?: number;
    navigation?: { nextEl: string; prevEl: string };
}

export interface SwiperConstructor {
    new(selector: string, options: SwiperOptions): object;
}
