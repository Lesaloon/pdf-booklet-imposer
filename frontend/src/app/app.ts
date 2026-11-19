import { ChangeDetectionStrategy, Component, computed, inject, OnDestroy, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { HlmButton } from '@spartan-ng/helm/button';
import { HlmNativeSelect } from '@spartan-ng/helm/native-select';

interface PaperFormat {
  input: string;
  input_mm: number[];
  sheet: string;
  sheet_mm: number[];
}
interface Result {
  url: string;
  filename: string;
  sheets: number;
  blanks: number;
  pages: number;
}

@Component({
  selector: 'app-root',
  imports: [HlmButton, HlmNativeSelect],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App implements OnDestroy {
  private readonly http = inject(HttpClient);
  readonly formats = signal<PaperFormat[]>([]);
  readonly format = signal('A6');
  readonly selected = computed(() => this.formats().find(item => item.input === this.format()));
  readonly file = signal<File | null>(null);
  readonly busy = signal(false);
  readonly loading = signal(true);
  readonly dragging = signal(false);
  readonly error = signal('');
  readonly result = signal<Result | null>(null);
  readonly maxBytes = signal(95 * 1024 * 1024);
  readonly maxMb = computed(() => this.maxBytes() / 1024 / 1024);

  constructor() {
    void this.loadFormats();
  }

  async loadFormats() {
    this.loading.set(true);
    this.error.set('');
    try {
      const data = await firstValueFrom(this.http.get<{formats: PaperFormat[]; max_upload_bytes: number}>('/api/formats'));
      this.formats.set(data.formats);
      this.maxBytes.set(data.max_upload_bytes);
    } catch {
      this.error.set('Could not connect to the converter. Please retry.');
    } finally {
      this.loading.set(false);
    }
  }

  chooseFile(event: Event) {
    const input = event.target as HTMLInputElement;
    this.setFile(input.files?.[0]);
    input.value = '';
  }

  drop(event: DragEvent) {
    event.preventDefault();
    this.dragging.set(false);
    this.setFile(event.dataTransfer?.files[0]);
  }

  setFile(file?: File) {
    if (this.busy() || !file) return;
    this.clearResult();
    this.error.set('');
    this.file.set(null);
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.error.set('Choose a PDF file.');
    } else if (file.size > this.maxBytes()) {
      this.error.set(`Choose a PDF smaller than ${this.maxMb()} MB.`);
    } else if (!file.size) {
      this.error.set('This file is empty. Choose a PDF with pages.');
    } else {
      this.file.set(file);
    }
  }

  changeFormat(value: string | null | undefined) {
    if (!value || this.busy()) return;
    this.format.set(value);
    this.clearResult();
    this.error.set('');
  }

  async convert() {
    const file = this.file();
    if (!file || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.clearResult();
    const body = new FormData();
    body.append('file', file);
    try {
      const response = await firstValueFrom(this.http.post(`/api/booklet?page_format=${this.format()}`, body, {
        observe: 'response', responseType: 'blob',
      }));
      if (!response.body) throw new Error('No PDF returned');
      this.result.set({
        url: URL.createObjectURL(response.body),
        filename: `${file.name.replace(/\.pdf$/i, '')}-booklet-${this.selected()?.sheet}.pdf`,
        sheets: Number(response.headers.get('X-Booklet-Sheets')),
        blanks: Number(response.headers.get('X-Booklet-Blanks')),
        pages: Number(response.headers.get('X-Booklet-Pages')),
      });
    } catch (error) {
      let message = 'Could not create your booklet. Please try again.';
      if (error instanceof HttpErrorResponse) {
        if (error.status === 0) message = 'Connection lost. Check your connection and try again.';
        else if (error.status === 413) message = `Choose a PDF smaller than ${this.maxMb()} MB.`;
        else if (error.error instanceof Blob) {
          try {
            const data = JSON.parse(await error.error.text());
            if (typeof data.detail === 'string') message = data.detail;
          } catch { /* A proxy may return a non-JSON error. */ }
        }
      }
      this.error.set(message);
    } finally {
      this.busy.set(false);
    }
  }

  private clearResult() {
    const result = this.result();
    if (result) URL.revokeObjectURL(result.url);
    this.result.set(null);
  }

  ngOnDestroy() { this.clearResult(); }
}
