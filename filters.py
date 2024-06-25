# filters.py

from telegram import Message

class Filters:
    @staticmethod
    def text(message: Message) -> bool:
        """
        Filter messages that contain text.
        """
        return message.text is not None

    @staticmethod
    def command(message: Message) -> bool:
        """
        Filter messages that are commands.
        """
        return message.text is not None and message.text.startswith('/')

    @staticmethod
    def custom_filter(condition):
        """
        Filter messages based on a custom condition function.
        :param condition: A function that takes a message and returns True or False.
        """
        def filter_func(message: Message) -> bool:
            return condition(message)
        return filter_func
