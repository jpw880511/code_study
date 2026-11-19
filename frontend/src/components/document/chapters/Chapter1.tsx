import type { Chapter1 as Chapter1Content } from '../../../services/document-service'

// All document text is rendered as React text nodes, never as HTML.
export default function Chapter1({ chapter }: { chapter: Chapter1Content }) {
  return (
    <section className="grid gap-3">
      <h3 className="text-lg font-semibold">{chapter.title}</h3>
      <p className="whitespace-pre-wrap">{chapter.summary}</p>
    </section>
  )
}
