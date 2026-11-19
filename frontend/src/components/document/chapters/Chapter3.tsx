import type { Chapter3 as Chapter3Content } from '../../../services/document-service'

export default function Chapter3({ chapter }: { chapter: Chapter3Content }) {
  return (
    <section className="grid gap-3">
      <h3 className="text-lg font-semibold">{chapter.title}</h3>
      <pre
        role="region"
        aria-label="순서도"
        tabIndex={0}
        className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-sm"
      >
        {chapter.flowchart}
      </pre>
      <dl className="grid gap-2 text-sm">
        {Object.entries(chapter.file_breakdown).map(([path, description]) => (
          <div key={path}>
            <dt className="font-medium">{path}</dt>
            <dd className="whitespace-pre-wrap">{description}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
