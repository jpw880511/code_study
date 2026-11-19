import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Chapter2 as Chapter2Content } from '../../../services/document-service'

const MAX_CARDS = 5

export default function Chapter2({ chapter }: { chapter: Chapter2Content }) {
  return (
    <section className="grid gap-3">
      <h3 className="text-lg font-semibold">{chapter.title}</h3>
      <ul className="grid gap-3">
        {chapter.concepts.slice(0, MAX_CARDS).map((concept) => (
          <li key={concept.name} aria-label={concept.name}>
            <Card>
              <CardHeader>
                <CardTitle>
                  <h4>{concept.name}</h4>
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <p className="whitespace-pre-wrap">{concept.explanation}</p>
                <div>
                  <p className="font-medium">비유</p>
                  <p className="whitespace-pre-wrap">{concept.analogy}</p>
                </div>
                <div>
                  <p className="font-medium">예시</p>
                  <pre className="overflow-x-auto rounded-md bg-muted p-2 whitespace-pre-wrap">
                    {concept.example}
                  </pre>
                </div>
                <div>
                  <p className="font-medium">활용 예</p>
                  <p className="whitespace-pre-wrap">{concept.use_cases}</p>
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}
