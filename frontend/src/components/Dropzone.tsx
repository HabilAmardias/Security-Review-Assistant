import { useRef, useState } from 'react'
import { CloudArrowUp, FileMd, FilePdf, FileTxt } from '@phosphor-icons/react'

interface Props {
  label: string
  accept?: string
  hint?: string
  locked?: boolean
  onFile: (file: File) => void
}

function fileKind(name: string): 'pdf' | 'md' | 'txt' | 'other' {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'pdf') return 'pdf'
  if (ext === 'md' || ext === 'markdown') return 'md'
  if (ext === 'txt') return 'txt'
  return 'other'
}

const KIND_META = {
  pdf: { icon: FilePdf, cls: 'text-destructive' },
  md: { icon: FileMd, cls: 'text-secondary' },
  txt: { icon: FileTxt, cls: 'text-foreground/60' },
  other: { icon: FileTxt, cls: 'text-foreground/60' },
}

export function Dropzone({
  label,
  accept = '.pdf',
  hint,
  locked = false,
  onFile,
}: Props) {
  const [over, setOver] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const kind = fileKind(fileName ?? '')
  const { icon: FileIcon, cls } = KIND_META[kind]

  return (
    <div>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          const file = e.dataTransfer.files?.[0]
          if (file) {
            setFileName(file.name)
            onFile(file)
          }
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors duration-150 ${
          over
            ? 'border-secondary bg-secondary/5'
            : 'border-border bg-background hover:border-secondary/50'
        }`}
      >
        {fileName ? (
          <>
            <FileIcon size={32} className={cls} />
            <p className="text-sm font-medium">{fileName}</p>
            <p className="text-xs text-foreground/50">Click or drop to replace</p>
          </>
        ) : (
          <>
            <CloudArrowUp size={32} className="text-foreground/40" />
            <p className="text-sm font-medium">{label}</p>
            <p className="text-xs text-foreground/50">{hint ?? 'PDF · click to browse or drop'}</p>
          </>
        )}
        {locked && (
          <span className="rounded-full bg-warning/10 px-2.5 py-0.5 text-xs text-warning">
            Locked — password required
          </span>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) {
            setFileName(file.name)
            onFile(file)
          }
        }}
      />
    </div>
  )
}
