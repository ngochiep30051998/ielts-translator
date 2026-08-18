import type { Plugin } from 'vite';

/**
 * Kiểu cho `sw-build-id.mjs`.
 *
 * Khai tay chứ không sinh từ TS: bản thật viết bằng JS để khỏi cần `@types/node` (xem
 * docstring bên đó). Sửa một bên thì sửa cả hai — không có gì tự bắt lỗi lệch nhau ngoài
 * `sw-build-id.test.ts`.
 */

export declare const BUILD_ID_TOKEN: string;
export declare function buildIdFrom(fileNames: Iterable<string>): string;
export declare function stampBuildId(source: string, buildId: string): string;
export declare function swBuildId(): Plugin;
