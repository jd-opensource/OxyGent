import os
import sys
# 获取项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append('..')

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from markitdown import MarkItDown
import io
from typing import BinaryIO, Any
import camelot
import tempfile
from markitdown.converters import PdfConverter
from markitdown.converters import AudioConverter
from markitdown.converters._pdf_converter import _dependency_exc_info
from markitdown.converters._exiftool import exiftool_metadata
from markitdown._stream_info import StreamInfo
from markitdown._base_converter import DocumentConverterResult
from markitdown._exceptions import MissingDependencyException, MISSING_DEPENDENCY_MESSAGE
import pdfminer
import pdfminer.high_level
import logging
logger = logging.getLogger(__name__)

from openai import OpenAI
import httpx
import base64, requests
import whisper

print('++++++++++++loading Audio Model+++++++++++++++')
whisper_model = whisper.load_model("base")

mcp = FastMCP()

_DEEP_ANALYZER_DESCRIPTION = """A tool that performs systematic, step-by-step analysis or calculation of a given task, optionally leveraging information from external resources such as attached file or uri to provide comprehensive reasoning and answers.
* At least one of `task` or `source` must be provided. When both are available, the tool will analyze and solve the task in the context of the provided source.
* The `source` can be a local file path or an uri. Support file extensions and uri are as follows:
 - Text: txt, doc, docx, ppt, pptx, csv, pdf, json, jsonl, jsonld, py, pdb, xml...
 - Image: png, jpg, jpeg...
 - Audio: mp3, m4a, wav...
 - Video: mp4, mov...
 - Archive: zip, rar... (NOTE: DO NOT need to unpack the archive, this tool will automatically handle it.)
 - Uri: https://xx.html, http://xx.htm, http://xx.pdf, file://xx, data://...
"""

_DEEP_ANALYZER_INSTRUCTION = """You should step-by-step analyze the task and/or the attached content.
* When the task involves playing a game or performing calculations. Please consider the conditions imposed by the game or calculation rules. You may take extreme conditions into account.
* When the task involves spelling words, you must ensure that the spelling rules are followed and that the resulting word is meaningful.
* When the task involves compute the area in a specific polygon. You should separate the polygon into sub-polygons and ensure that the area of each sub-polygon is computable (e.g, rectangle, circle, triangle, etc.). Step-by-step to compute the area of each sub-polygon and sum them up to get the final area.
* When the task involves calculation and statistics, it is essential to consider all constraints. Failing to account for these constraints can easily lead to statistical errors.

Here is the task:
"""

_DEEP_ANALYZER_SUMMARY_DESCRIPTION = """Please conduct a step-by-step analysis of the outputs from different models. Compare their results, identify discrepancies, extract the accurate components, eliminate the incorrect ones, and synthesize a coherent summary."""


def source_to_bytes(source: str):
    if source.startswith('http'):
        with httpx.Client() as client:
            response = client.get(source)
            response.raise_for_status()
            return response.content
    else:
        with open(source, 'rb') as f:
            return f.read()


def video_to_base64(source: str, max_video_size: int = 512 * 1024 * 1024) -> str:
    video_bytes = source_to_bytes(source)
    if len(video_bytes) > max_video_size:
        return source
    else:
        base64_str = base64.b64encode(video_bytes).decode('utf-8')
        return base64_str


def audio_to_base64(source: str) -> str:
    audio_bytes = source_to_bytes(source)
    base64_str = base64.b64encode(audio_bytes).decode('utf-8')
    return base64_str


def read_tables_from_stream(file_stream):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp_pdf:
        temp_pdf.write(file_stream.read())
        temp_pdf.flush()
        tables = camelot.read_pdf(temp_pdf.name, flavor="lattice")
        return tables


def encode_base64_content_from_url(content_url: str) -> str:
    """Encode a content retrieved from a remote url to base64 format."""

    with requests.get(content_url) as response:
        response.raise_for_status()
        result = base64.b64encode(response.content).decode("utf-8")

    return result


def transcribe_video(file_stream):
    client = OpenAI(
        base_url=os.getenv('OPEN_AI_URL'),
        api_key=os.getenv('OPEN_AI_KEY'),
    )
    video_base64 = video_to_base64(file_stream, 12 * 1024 * 1024)
    chat_completion_from_base64 = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this video?"},
                    {
                        "type": "video_url",
                        "video_url": {"url": f"data:video/mp4;base64,{video_base64}"},
                    },
                ],
            }
        ],
        model=os.getenv('GLM_4V_PLUS'),
    )

    result = chat_completion_from_base64.choices[0].message.content
    print("Chat completion output from input video:", result)
    return result


class AudioWhisperConverter(AudioConverter):

    def convert(
            self,
            file_stream: BinaryIO,
            stream_info: StreamInfo,
            **kwargs: Any,  # Options to pass to the converter
    ) -> DocumentConverterResult:
        md_content = ""

        # Add metadata
        metadata = exiftool_metadata(
            file_stream, exiftool_path=kwargs.get("exiftool_path")
        )
        if metadata:
            for f in [
                "Title",
                "Artist",
                "Author",
                "Band",
                "Album",
                "Genre",
                "Track",
                "DateTimeOriginal",
                "CreateDate",
                # "Duration", -- Wrong values when read from memory
                "NumChannels",
                "SampleRate",
                "AvgBytesPerSec",
                "BitsPerSample",
            ]:
                if f in metadata:
                    md_content += f"{f}: {metadata[f]}\n"

        # Figure out the audio format for transcription
        if stream_info.extension == ".wav" or stream_info.mimetype == "audio/x-wav":
            audio_format = "wav"
        elif stream_info.extension == ".mp3" or stream_info.mimetype == "audio/mpeg":
            audio_format = "mp3"
        elif (
                stream_info.extension in [".mp4", ".m4a"]
                or stream_info.mimetype == "video/mp4"
        ):
            audio_format = "mp4"
        else:
            audio_format = None

        # Transcribe
        if audio_format in ["wav", "mp3"]:
            md_content += whisper_model.transcribe(file_stream.name)['text']
        elif audio_format in ["mp4"]:
            md_content += transcribe_video(file_stream.name)
        else:
            print("Error: ", stream_info.extension)

        # Return the result
        return DocumentConverterResult(markdown=md_content.strip())


class PdfWithTableConverter(PdfConverter):
    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,  # Options to pass to the converter
    ) -> DocumentConverterResult:
        # Check the dependencies
        if _dependency_exc_info is not None:
            raise MissingDependencyException(
                MISSING_DEPENDENCY_MESSAGE.format(
                    converter=type(self).__name__,
                    extension=".pdf",
                    feature="pdf",
                )
            ) from _dependency_exc_info[
                1
            ].with_traceback(  # type: ignore[union-attr]
                _dependency_exc_info[2]
            )

        assert isinstance(file_stream, io.IOBase)  # for mypy

        tables = read_tables_from_stream(file_stream)
        num_tables = tables.n
        if num_tables == 0:
            return DocumentConverterResult(
                markdown=pdfminer.high_level.extract_text(file_stream),
            )
        else:
            markdown_content = pdfminer.high_level.extract_text(file_stream)
            table_content = ""
            for i in range(num_tables):
                table = tables[i].df
                table_content += f"Table {i + 1}:\n" + table.to_markdown(index=False) + "\n\n"
            markdown_content += "\n\n" + table_content
            return DocumentConverterResult(
                markdown=markdown_content,
            )


class MarkitdownConverter:
    def __init__(self,
                 use_llm: bool = False,
                 timeout: int = 30):

        self.timeout = timeout
        self.use_llm = use_llm

        if use_llm:
            client = OpenAI(
                base_url=os.getenv('DEEPSEEK_URL'),
                api_key=os.getenv('DEEPSEEK_KEY'),
            )
            self.client = MarkItDown(
                enable_plugins=True,
                llm_client=client,
                llm_model=os.getenv('DEEPSEEK_V3'),
            )
        else:
            self.client = MarkItDown(
                enable_plugins=True,
            )

        removed_converters = [
            PdfConverter, AudioConverter
        ]

        self.client._converters = [
            converter for converter in self.client._converters
            if not isinstance(converter.converter, tuple(removed_converters))
        ]
        self.client.register_converter(PdfWithTableConverter())
        self.client.register_converter(AudioWhisperConverter())

    def convert(self, source, **kwargs: Any):
        try:
            result = self.client.convert(
                source,
                **kwargs)
            return result
        except Exception as e:
            logger.error(f"Error during conversion: {e}")
            return None






