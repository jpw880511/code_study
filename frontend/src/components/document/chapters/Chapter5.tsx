import type { Chapter5 as Chapter5Content } from '../../../services/document-service'

export default function Chapter5({ chapter }: { chapter: Chapter5Content }) {
  return (
    <section className="grid gap-3">
      <h3 className="text-lg font-semibold">{chapter.title}</h3>
      <ol className="grid gap-3">
        {chapter.steps.map((step) => (
          <li key={step.step} className="grid gap-1 rounded-lg border p-3 text-sm">
            <p className="font-medium">{step.step}단계</p>
            <p className="whitespace-pre-wrap">{step.description}</p>
            {step.data && (
              <pre className="overflow-x-auto rounded-md bg-muted p-2 font-mono whitespace-pre-wrap">
                {step.data}
              </pre>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
