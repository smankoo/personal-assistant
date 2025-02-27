import abc


class LLMClient(abc.ABC):
    @abc.abstractmethod
    def stream_response(self, prompt: str):
        """
        Given a prompt string, stream the response as an iterator of text chunks.
        """
        pass
