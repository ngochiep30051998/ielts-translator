import { defineManifest } from '@crxjs/vite-plugin';

export default defineManifest({
  manifest_version: 3,
  name: 'IELTS Translator',
  version: '0.1.0',
  description: 'Dịch hai chiều Việt-Anh chuẩn IELTS band 6.5+ và học từ mới',
  key: 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAycO1Wb9FLs24mQE8eIJzmEOlldeUHj9Eh5YbZ5Zk/N3D5TJNMvqL6P+gYVmM4jct8YF1NkY5DDrtKRXzp7JRa4Feh2l/7Hyt/RQkMJjvBjk+KpPBl1tfEY+KZ+U6yjApc/fSZLPQ5F/DUtIwO6At/HNmfe8hI6mSC3X+vsIx9ijXpeADBMqLDswDCTrz2CkgYKitMUWRjBbK3Utz1+9fgtDwuV8MNMZlbkqsOP2wIQx5OnWxx7pqn/MK7cUFrAaAnORoqPEuAmXsnHIUkklVxVsod9iaKua1aBn/2HgY+aND+KaVqT3WB/Ednl4KkiO7lUtOvpUzJsg78+/F285pZwIDAQAB',
  permissions: ['storage', 'sidePanel'],
  host_permissions: ['http://127.0.0.1:8080/*'],
  action: { default_title: 'IELTS Translator' },
  background: { service_worker: 'src/background/service-worker.ts', type: 'module' },
  side_panel: { default_path: 'src/sidepanel/index.html' },
  options_page: 'src/options/index.html',
  content_scripts: [
    {
      matches: ['<all_urls>'],
      js: ['src/content/index.ts'],
      run_at: 'document_idle',
    },
  ],
  commands: {
    'translate-selection': {
      suggested_key: { default: 'Alt+T' },
      description: 'Dịch đoạn đang bôi đen',
    },
  },
});
