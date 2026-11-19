// Client-side checks for fast feedback only; the server stays the authority. They mirror
// the server's rules: password of 8+ characters with a letter and a digit, at most 72 bytes
// in UTF-8 (a Korean character takes 3 bytes).

export const MAX_PASSWORD_BYTES = 72
export const MIN_PASSWORD_LENGTH = 8

const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateEmail(email: string): string | undefined {
  if (email === '') return '이메일을 입력하세요.'
  if (!EMAIL_SHAPE.test(email)) return '올바른 이메일 형식이 아닙니다.'
}

export function validateLoginPassword(password: string): string | undefined {
  if (password === '') return '비밀번호를 입력하세요.'
}

export function validateNewPassword(password: string): string | undefined {
  if (password === '') return '비밀번호를 입력하세요.'
  if (password.length < MIN_PASSWORD_LENGTH) return '비밀번호는 8자 이상이어야 합니다.'
  if (!/\p{L}/u.test(password)) return '비밀번호에 영문자를 포함하세요.'
  if (!/\d/.test(password)) return '비밀번호에 숫자를 포함하세요.'
  if (new TextEncoder().encode(password).length > MAX_PASSWORD_BYTES) {
    return '비밀번호는 72바이트 이하여야 합니다. (한글은 글자당 3바이트)'
  }
}

export function validatePasswordConfirmation(
  password: string,
  confirmation: string,
): string | undefined {
  if (confirmation === '') return '비밀번호 확인을 입력하세요.'
  if (confirmation !== password) return '비밀번호가 일치하지 않습니다.'
}
