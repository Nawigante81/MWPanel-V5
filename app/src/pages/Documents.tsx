import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Upload, Download, Trash2, FileText, ImageIcon, Folder, CheckSquare, X, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { documentsApi, type DocumentApi } from '@/lib/api';

type UploadTask = {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'retrying' | 'done' | 'error';
  retries: number;
  progress: number;
  error?: string;
};

const formatBytes = (bytes: number) => {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let b = bytes;
  while (b >= 1024 && i < units.length - 1) {
    b /= 1024;
    i += 1;
  }
  return `${b.toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
};

const allowedMime = new Set([
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/webp',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-excel',
  'text/plain',
]);

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function Documents() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const processingRef = useRef(false);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<UploadTask[]>([]);
  const [deleteAllOpen, setDeleteAllOpen] = useState(false);
  const [deleteAllText, setDeleteAllText] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const offset = (page - 1) * pageSize;
  const { data, isLoading } = useQuery({
    queryKey: ['documents', { page, pageSize, search }],
    queryFn: () => documentsApi.list({ limit: pageSize, offset, q: search || undefined }),
    refetchInterval: 15000,
  });

  const pageItems = (data?.documents || []) as DocumentApi[];
  const total = Number(data?.total || 0);
  const stats = data?.stats || { total: 0, pdf: 0, images: 0, total_size_bytes: 0 };
  const pages = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    if (page > pages) setPage(pages);
  }, [page, pages]);

  const updateTask = (id: string, patch: Partial<UploadTask>) => {
    setUploadQueue((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  };

  const runQueue = async (queued?: UploadTask[]) => {
    if (processingRef.current) return;
    processingRef.current = true;

    const tasks = queued ? [...queued] : [...uploadQueue];
    for (const task of tasks) {
      if (task.status === 'done') continue;

      let success = false;
      let attempt = 0;
      while (!success && attempt < 3) {
        attempt += 1;
        updateTask(task.id, {
          status: attempt === 1 ? 'uploading' : 'retrying',
          retries: attempt - 1,
          progress: 0,
          error: undefined,
        });

        try {
          const res = await documentsApi.upload([task.file], undefined, (p) => updateTask(task.id, { progress: p }));
          if ((res?.errors || []).length) {
            throw new Error(res.errors[0]?.error || 'Upload error');
          }
          updateTask(task.id, { status: 'done', progress: 100 });
          success = true;
        } catch (e: any) {
          if (attempt < 3) {
            await sleep(1000 * attempt);
          } else {
            updateTask(task.id, { status: 'error', error: e?.message || 'Błąd uploadu' });
          }
        }
      }
    }

    processingRef.current = false;
    await queryClient.invalidateQueries({ queryKey: ['documents'] });
    toast.success('Kolejka uploadu zakończona.');
  };

  const enqueueFiles = (fileList: FileList | null) => {
    if (!fileList || !fileList.length) return;
    const files = Array.from(fileList);
    const invalid = files.filter((f) => !allowedMime.has(f.type));
    if (invalid.length) {
      toast.error(`Niedozwolony typ: ${invalid.map((f) => f.name).join(', ')}`);
    }

    const valid = files.filter((f) => allowedMime.has(f.type));
    if (!valid.length) return;

    const queued = valid.map((f) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file: f,
      status: 'pending' as const,
      retries: 0,
      progress: 0,
    }));

    setUploadQueue((prev) => [...prev, ...queued]);
    setUploadOpen(true);

    setTimeout(() => {
      runQueue(queued);
    }, 10);
  };

  const retryFailed = () => {
    setUploadQueue((prev) => prev.map((t) => (t.status === 'error' ? { ...t, status: 'pending', retries: 0, progress: 0, error: undefined } : t)));
    setTimeout(() => runQueue(), 10);
  };

  const deleteOneMutation = useMutation({
    mutationFn: (id: string) => documentsApi.deleteOne(id),
    onSuccess: () => {
      toast.success('Dokument usunięty');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  const deleteBulkMutation = useMutation({
    mutationFn: (ids: string[]) => documentsApi.deleteBulk(ids),
    onSuccess: () => {
      toast.success('Usunięto zaznaczone dokumenty');
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  const deleteAllMutation = useMutation({
    mutationFn: () => documentsApi.deleteAll(),
    onSuccess: () => {
      toast.success('Usunięto wszystkie dokumenty');
      setDeleteAllOpen(false);
      setDeleteAllText('');
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  const toggle = (id: string) => {
    const n = new Set(selected);
    if (n.has(id)) n.delete(id);
    else n.add(id);
    setSelected(n);
  };

  const toggleAllPage = () => {
    const pageIds = pageItems.map((d) => d.id);
    const allSelected = pageIds.every((id) => selected.has(id));
    const n = new Set(selected);
    if (allSelected) pageIds.forEach((id) => n.delete(id));
    else pageIds.forEach((id) => n.add(id));
    setSelected(n);
  };

  const bulkDownload = async () => {
    if (!selected.size) return;
    const blob = await documentsApi.bulkDownload(Array.from(selected));
    downloadBlob(blob, 'documents.zip');
  };

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Ładowanie dokumentów...</div>;
  }

  const hasFailedInQueue = uploadQueue.some((q) => q.status === 'error');

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dokumenty</h1>
          <p className="text-muted-foreground">Upload, miniatury, paginacja, pobieranie i usuwanie.</p>
        </div>
        <div className="flex gap-2">
          <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
            <DialogTrigger asChild>
              <Button><Upload className="w-4 h-4 mr-2" />Prześlij plik</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Prześlij dokumenty</DialogTitle></DialogHeader>
              <div
                className="border-2 border-dashed rounded-xl p-6 text-center"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  enqueueFiles(e.dataTransfer.files);
                }}
              >
                <p className="font-medium">Przeciągnij pliki tutaj</p>
                <p className="text-sm text-muted-foreground mb-3">albo wybierz z dysku</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => enqueueFiles(e.target.files)}
                />
                <Button variant="outline" onClick={() => fileInputRef.current?.click()}>Wybierz pliki</Button>
                <p className="text-xs text-muted-foreground mt-2">PDF, JPG/PNG/WEBP, DOC/DOCX, XLS/XLSX, TXT • max 50MB</p>
              </div>

              {!!uploadQueue.length && (
                <div className="space-y-2 max-h-48 overflow-auto border rounded-lg p-2">
                  {uploadQueue.map((q) => (
                    <div key={q.id} className="text-xs flex items-center justify-between gap-2">
                      <span className="truncate">{q.file.name}</span>
                      <span>
                        {q.status === 'uploading' && `upload ${q.progress}%`}
                        {q.status === 'retrying' && `retry ${q.retries}/2 ${q.progress}%`}
                        {q.status === 'done' && '✓'}
                        {q.status === 'error' && '✗'}
                        {q.status === 'pending' && 'kolejka'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {hasFailedInQueue && (
                <Button variant="outline" onClick={retryFailed}><RefreshCw className="w-4 h-4 mr-1" />Ponów nieudane</Button>
              )}
            </DialogContent>
          </Dialog>

          <Dialog open={deleteAllOpen} onOpenChange={setDeleteAllOpen}>
            <DialogTrigger asChild>
              <Button variant="destructive">Usuń wszystko</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Usuń wszystkie dokumenty</DialogTitle></DialogHeader>
              <p className="text-sm text-muted-foreground">Wpisz <b>USUŃ</b>, aby potwierdzić.</p>
              <Input value={deleteAllText} onChange={(e) => setDeleteAllText(e.target.value)} />
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setDeleteAllOpen(false)}>Anuluj</Button>
                <Button variant="destructive" disabled={deleteAllText !== 'USUŃ'} onClick={() => deleteAllMutation.mutate()}>
                  Potwierdź usunięcie
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Card><CardContent className="p-4 flex items-center gap-3"><Folder className="w-5 h-5 text-blue-600" /><div><div className="text-xl font-bold">{stats.total}</div><div className="text-xs text-muted-foreground">Dokumenty</div></div></CardContent></Card>
        <Card><CardContent className="p-4 flex items-center gap-3"><FileText className="w-5 h-5 text-rose-600" /><div><div className="text-xl font-bold">{stats.pdf}</div><div className="text-xs text-muted-foreground">Pliki PDF</div></div></CardContent></Card>
        <Card><CardContent className="p-4 flex items-center gap-3"><ImageIcon className="w-5 h-5 text-purple-600" /><div><div className="text-xl font-bold">{stats.images}</div><div className="text-xs text-muted-foreground">Zdjęcia</div></div></CardContent></Card>
        <Card><CardContent className="p-4 flex items-center gap-3"><FileText className="w-5 h-5 text-emerald-600" /><div><div className="text-xl font-bold">{formatBytes(stats.total_size_bytes)}</div><div className="text-xs text-muted-foreground">Całkowity rozmiar</div></div></CardContent></Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <div className="flex flex-col md:flex-row gap-2 md:items-center md:justify-between">
            <Input placeholder="Szukaj dokumentów..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} className="max-w-md" />
            <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(1); }}>
              <SelectTrigger className="w-36"><SelectValue placeholder="Na stronę" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10 / str.</SelectItem>
                <SelectItem value="20">20 / str.</SelectItem>
                <SelectItem value="50">50 / str.</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {selected.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 p-2 rounded-lg bg-primary/5">
              <CheckSquare className="w-4 h-4" />
              <span className="text-sm">Zaznaczono: {selected.size}</span>
              <Button size="sm" variant="outline" onClick={bulkDownload}><Download className="w-4 h-4 mr-1" />Pobierz ZIP</Button>
              <Button size="sm" variant="destructive" onClick={() => deleteBulkMutation.mutate(Array.from(selected))}><Trash2 className="w-4 h-4 mr-1" />Usuń zaznaczone</Button>
              <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}><X className="w-4 h-4 mr-1" />Wyczyść</Button>
            </div>
          )}

          <div className="border rounded-lg overflow-hidden">
            <div className="grid grid-cols-12 p-2 bg-muted/40 text-xs font-medium">
              <div className="col-span-1"><Checkbox checked={pageItems.length > 0 && pageItems.every((d) => selected.has(d.id))} onCheckedChange={toggleAllPage} /></div>
              <div className="col-span-2">Podgląd</div>
              <div className="col-span-4">Nazwa</div>
              <div className="col-span-2">Typ</div>
              <div className="col-span-1">Rozmiar</div>
              <div className="col-span-2 text-right">Akcje</div>
            </div>
            {pageItems.map((d) => {
              const isImage = String(d.mime_type || '').startsWith('image/');
              return (
                <div key={d.id} className="grid grid-cols-12 p-2 border-t items-center text-sm">
                  <div className="col-span-1"><Checkbox checked={selected.has(d.id)} onCheckedChange={() => toggle(d.id)} /></div>
                  <div className="col-span-2">
                    {isImage ? (
                      <img src={documentsApi.downloadOneUrl(d.id)} alt={d.name} className="h-10 w-14 object-cover rounded border" loading="lazy" />
                    ) : (
                      <div className="h-10 w-14 rounded border flex items-center justify-center text-[10px] text-muted-foreground">Brak</div>
                    )}
                  </div>
                  <div className="col-span-4 min-w-0">
                    <div className="truncate">{d.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{d.related_to || '-'}</div>
                  </div>
                  <div className="col-span-2"><Badge variant="secondary" className="text-[10px] max-w-full truncate">{d.mime_type || '-'}</Badge></div>
                  <div className="col-span-1">{formatBytes(Number(d.size_bytes || 0))}</div>
                  <div className="col-span-2 flex justify-end gap-1">
                    <Button size="icon" variant="ghost" asChild>
                      <a href={documentsApi.downloadOneUrl(d.id)} target="_blank" rel="noreferrer"><Download className="w-4 h-4" /></a>
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => deleteOneMutation.mutate(d.id)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
                  </div>
                </div>
              );
            })}
            {!pageItems.length && <div className="p-6 text-sm text-muted-foreground text-center">Brak dokumentów.</div>}
          </div>

          <div className="flex items-center justify-between text-sm">
            <div className="text-muted-foreground">
              Strona {page} z {pages} • rekordy {total ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, total)} z {total}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</Button>
              <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage((p) => Math.min(pages, p + 1))}>Next</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
