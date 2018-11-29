import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')


class Person:
    """Silly Person"""

    def __new__(cls, name, age):
        # print('__new__ called.')
        logging.info('__new__ log')
        return super().__new__(cls)

    def __init__(self, name, age):
        # print('__init__ called.')
        logging.info('__init__ log')
        self.name = name
        self.age = age

    def __str__(self):
        return '<Person: %s(%s)>' % (self.name, self.age)


class Hello:
    def hello(self, name='world'):
        print('Hello, %s.' % name)


def fn(self, name='world'):
    print('Hello, %s.' % name)


if __name__ == '__main__':
    piglei = Person('piglei', 24)
    logging.info(piglei)
    # Hello2 = type('Hello', (object,), dict(hello=fn))
    # h2 = Hello2()
    # h2.hello()
