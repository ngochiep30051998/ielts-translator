/*
 * Vẽ icon extension bằng Node thuần (không thêm dependency): dựng ảnh RGBA rồi
 * đóng gói PNG thủ công. Hình khớp với icon nút dịch trong bubble (`content/bubble.ts`,
 * ICONS.translate) — nền bo góc màu nhấn, trên đó là một cuốn sách mở.
 *
 * Ở cỡ 16px không thể vẽ theo kiểu nét viền như bản SVG: nét 2px trên khung 24 co lại
 * còn hơn 1px và nhoè thành vệt xám. Nên bản PNG dùng khối ĐẶC, giữ lại đúng dấu hiệu
 * nhận ra cuốn sách: hai trang chếch lên ở mép ngoài và khe gáy ở giữa.
 *
 * Chạy lại khi đổi màu thương hiệu:  npm run icons
 */
import { deflateSync } from 'node:zlib';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Dùng chung cho cả extension lẫn web, nên KHÔNG chốt cứng cỡ và thư mục ra.
 *
 *   node scripts/make-icons.mjs --out apps/extension/public/icons --sizes 16,32,48,128
 *   node scripts/make-icons.mjs --out apps/web/public/icons       --sizes 192,512
 *
 * Chép đôi file này cho web sẽ tạo hai bộ icon lệch nhau ngay lần đầu ai đó đổi màu thương
 * hiệu — và lệch ở chỗ không ai nghĩ tới việc đi kiểm.
 */
function doiSo(ten, macDinh) {
  const i = process.argv.indexOf(`--${ten}`);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : macDinh;
}

const GOC_REPO = join(dirname(fileURLToPath(import.meta.url)), '..');
const SIZES = doiSo('sizes', '16,32,48,128').split(',').map((n) => Number(n.trim()));
const OUT_DIR = join(GOC_REPO, doiSo('out', 'apps/extension/public/icons'));

if (SIZES.some((n) => !Number.isInteger(n) || n <= 0)) {
  console.error(`--sizes không hợp lệ: ${doiSo('sizes', '')}`);
  process.exit(1);
}

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

/**
 * Trang sách bên TRÁI, 4 đỉnh theo chiều kim đồng hồ (trục y hướng xuống).
 *
 * Trang phải là ảnh gương qua x = 0.5, lấy bằng cách soi `1 - x` vào chính đa giác này
 * — đối xứng tuyệt đối, không phải hai bộ toạ độ chép tay dễ lệch nhau.
 *
 * Khe giữa hai trang rộng 0.09 (≈1.4px ở cỡ 16) — chính khe hở màu nền này làm hình đọc
 * ra "sách mở"; hẹp hơn thì ở cỡ 16px nó dính thành một khối chữ nhật vô nghĩa.
 */
const PAGE = [
  [0.19, 0.32],
  [0.455, 0.39],
  [0.455, 0.72],
  [0.19, 0.65],
];

function insidePage(x, y) {
  for (let i = 0; i < PAGE.length; i++) {
    const [ax, ay] = PAGE[i];
    const [bx, by] = PAGE[(i + 1) % PAGE.length];
    if ((bx - ax) * (y - ay) - (by - ay) * (x - ax) < 0) return false;
  }
  return true;
}

/** Màu của một điểm mẫu, hoặc null nếu nằm ngoài hình. */
function sampleAt(x, y) {
  if (sdRoundSquare(x, y, 0.28) > 0) return null;
  return insidePage(x, y) || insidePage(1 - x, y) ? FG : BG;
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
