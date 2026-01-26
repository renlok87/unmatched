import { Scalar, CustomScalar } from '@nestjs/graphql';
import { Kind, ValueNode } from 'graphql';
import { GraphQLError } from 'graphql';

@Scalar('DateTime', () => Date)
export class DateTimeScalar implements CustomScalar<number, Date> {
  description = 'Date custom scalar type';

  parseValue(value: number): Date {
    return new Date(value); // value from client
  }

  serialize(value: unknown): number {
    if (value instanceof Date) {
      return value.getTime(); // value sent to client
    }
    throw new GraphQLError(`Cannot serialize value: ${typeof value}`);
  }

  parseLiteral(ast: ValueNode): Date {
    if (ast.kind === Kind.INT) {
      return new Date(ast.value);
    }
    throw new GraphQLError(`Cannot parse literal: ${ast.kind}`);
  }
}
