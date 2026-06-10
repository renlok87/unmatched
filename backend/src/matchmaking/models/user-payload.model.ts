/**
 * User Payload Model
 *
 * Представление авторизованного пользователя из JWT токена.
 */

export interface UserPayload {
  userId: string;
  email: string;
  username: string;
}
