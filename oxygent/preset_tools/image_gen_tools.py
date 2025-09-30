from oxygent.oxy import FunctionHub

image_gen_tools = FunctionHub(name="image_gen_tools")


@image_gen_tools.tool(
    description="An image generation service that takes text descriptions as input and returns a URL of the image,text "
                "descriptions only accept English, so you need to translate the description into English in advance."
)
def gen_image(description: str) -> str:
    """
    Image generation method, returns image URL
    """
    return f'https://image.pollinations.ai/prompt/{description}?nologo=true'
