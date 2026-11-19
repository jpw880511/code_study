// Client-side checks for fast feedback only; the server stays the authority. They mirror
// its rules: title 1-255 characters and description at most 2000, both after trimming.

export const MAX_TITLE_LENGTH = 255
export const MAX_DESCRIPTION_LENGTH = 2000

export function validateProjectTitle(title: string): string | undefined {
  const length = title.trim().length
  if (length < 1) return '프로젝트 제목은 최소 1자 이상이어야 합니다.'
  if (length > MAX_TITLE_LENGTH) return '프로젝트 제목은 최대 255자까지 입력 가능합니다.'
}

export function validateProjectDescription(description: string): string | undefined {
  if (description.trim().length > MAX_DESCRIPTION_LENGTH) {
    return '프로젝트 설명은 최대 2000자까지 입력 가능합니다.'
  }
}
