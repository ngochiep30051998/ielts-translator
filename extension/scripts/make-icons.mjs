/*
 * Vẽ icon extension bằng Node thuần (không thêm dependency): dựng ảnh RGBA rồi
 * đóng gói PNG thủ công. Hình lấy đúng dấu nhận diện dùng trong giao diện —
 * nền bo góc màu đất nung, vệt bút chéo và một chấm.
 *
 * Chạy lại khi đổi màu thương hiệu:  npm run icons
 */
import { deflateSync } from 'node:zlib';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SIZES = [16, 32, 48, 128];
const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'icons');

// Trùng --accent / --accent-soft trong src/sidepanel/styles.css
const BG = [0x4f, 0x46, 0xe5];
const FG = [0xee, 0xf0, 0xfe];
const SAMPLES = 4;

/* ── Hình học (toạ độ chuẩn hoá 0..1) ─────────────────────────────────── */

function sdRoundSquare(x, y, radius) {
  const dx = Math.abs(x - 0.5) - (0.5 - radius);
  const dy = Math.abs(y - 0.5) - (0.5 - radius);
  return (
    Math.hypot(Math.max(dx, 0), Math.max(dy, 0)) + Math.min(Math.max(dx, dy), 0) - radius
  );
}

function sdSegment(px, py, ax, ay, bx, by) {
  const vx = bx - ax;
  const vy = by - ay;
  const wx = px - ax;
  const wy = py - ay;
  const t = Math.min(1, Math.max(0, (wx * vx + wy * vy) / (vx * vx + vy * vy)));
  return Math.hypot(wx - t * vx, wy - t * vy);
}

/** Màu của một điểm mẫu, hoặc null nếu nằm ngoài hình. */
function sampleAt(x, y) {
  if (sdRoundSquare(x, y, 0.28) > 0) return null;
  const stroke = sdSegment(x, y, 0.33, 0.7, 0.7, 0.33) - 0.075;
  const dot = Math.hypot(x - 0.3, y - 0.315) - 0.085;
  return Math.min(stroke, dot) <= 0 ? FG : BG;
}

/** Khử răng cưa bằng cách lấy trung bình SAMPLES×SAMPLES điểm trong mỗi pixel. */
function render(size) {
  const pixels = Buffer.alloc(size * size * 4);
  const step = 1 / (size * SAMPLES);
  for (let py = 0; py < size; py++) {
    for (let px = 0; px < size; px++) {
      let r = 0;
      let g = 0;
      let b = 0;
      let hits = 0;
      for (let sy = 0; sy < SAMPLES; sy++) {
        for (let sx = 0; sx < SAMPLES; sx++) {
          const colour = sampleAt(
            (px * SAMPLES + sx + 0.5) * step,
            (py * SAMPLES + sy + 0.5) * step,
          );
          if (!colour) continue;
          r += colour[0];
          g += colour[1];
          b += colour[2];
          hits += 1;
        }
      }
      const at = (py * size + px) * 4;
      if (hits === 0) continue;
      pixels[at] = Math.round(r / hits);
      pixels[at + 1] = Math.round(g / hits);
      pixels[at + 2] = Math.round(b / hits);
      pixels[at + 3] = Math.round((hits / (SAMPLES * SAMPLES)) * 255);
    }
  }
  return pixels;
}

/* ── Đóng gói PNG ─────────────────────────────────────────────────────── */

const CRC_TABLE = Int32Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c;
});

function crc32(buffer) {
  let c = -1;
  for (const byte of buffer) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

function encodePng(size, pixels) {
  const stride = size * 4;
  const raw = Buffer.alloc((stride + 1) * size);
  for (let y = 0; y < size; y++) {
    raw[y * (stride + 1)] = 0; // filter: none
    pixels.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // truecolour + alpha

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

mkdirSync(OUT_DIR, { recursive: true });
for (const size of SIZES) {
  writeFileSync(join(OUT_DIR, `${size}.png`), encodePng(size, render(size)));
  process.stdout.write(`icons/${size}.png\n`);
}
