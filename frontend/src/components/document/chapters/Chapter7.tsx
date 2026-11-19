import type { Chapter7 as Chapter7Content } from '../../../services/document-service'

function Code({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="font-medium">{label}</p>
      <pre className="overflow-x-auto rounded-md bg-muted p-2 font-mono whitespace-pre-wrap">
        {text}
      </pre>
    </div>
  )
}

export default function Chapter7({ chapter }: { chapter: Chapter7Content }) {
  return (
    <section className="grid gap-3">
      <h3 className="text-lg font-semibold">{chapter.title}</h3>
      <ul className="grid gap-3">
        {chapter.mistakes.map((mistake, index) => (
          <li
            key={`${index}:${mistake.wrong}`}
            aria-label={`실수 ${index + 1}`}
            className="grid gap-2 rounded-lg border p-3 text-sm"
          >
            <Code label="잘못된 예" text={mistake.wrong} />
            <Code label="올바른 예" text={mistake.right} />
            <div>
              <p className="font-medium">이유</p>
              <p className="whitespace-pre-wrap">{mistake.why}</p>
            </div>
            <div>
              <p className="font-medium">고치는 법</p>
              <p className="whitespace-pre-wrap">{mistake.fix}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
