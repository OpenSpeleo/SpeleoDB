import type { AOSRuntime, SwiperConstructor } from '../domain/public-shell.ts';

declare global {
    var AOS: AOSRuntime;
    var Swiper: SwiperConstructor;
}
