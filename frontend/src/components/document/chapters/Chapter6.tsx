import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Chapter6 as Chapter6Content } from '../../../services/document-service'

export default function Chapter6({ chapter }: { chapter: Chapter6Content }) {
  return (
    <section className="grid gap-3">
      <h3 className="text-lg font-semibold">{chapter.title}</h3>
      <ul className="grid gap-3">
        {chapter.concepts.map((concept) => (
          <li key={concept.name} aria-label={concept.name}>
            <Card>
              <CardHeader>
                <CardTitle>
                  <h4>{concept.name}</h4>
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <div>
                  <p className="font-medium">무엇인가요</p>
                  <p className="whitespace-pre-wrap">{concept.what_it_is}</p>
                </div>
                <div>
                  <p className="font-medium">왜 쓰나요</p>
                  <p className="whitespace-pre-wrap">{concept.why_its_used}</p>
                </div>
                <div>
                  <p className="font-medium">어디에 쓰였나요</p>
                  <p className="whitespace-pre-wrap">{concept.where_its_applied}</p>
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}
