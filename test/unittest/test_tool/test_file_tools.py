import os
import pytest
import tempfile
import shutil

from oxygent.preset_tools.file_tools import write_file, read_file, delete_file


@pytest.mark.asyncio
async def test_write_file_create_new():
    """Test creating a new file with write_file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        content = "Hello, World!"
        result = await write_file(tmp_path, content)
        
        assert result == f"Successfully wrote to {tmp_path}"
        assert os.path.exists(tmp_path)
        
        with open(tmp_path, 'r', encoding='utf-8') as f:
            assert f.read() == content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_write_file_overwrite_existing():
    """Test overwriting an existing file with write_file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write("Old content")
    
    try:
        new_content = "New content"
        result = await write_file(tmp_path, new_content)
        
        assert result == f"Successfully wrote to {tmp_path}"
        
        with open(tmp_path, 'r', encoding='utf-8') as f:
            assert f.read() == new_content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_write_file_with_unicode():
    """Test writing file with unicode content."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        content = "你好，世界！\nHello, 世界！"
        result = await write_file(tmp_path, content)
        
        assert result == f"Successfully wrote to {tmp_path}"
        
        with open(tmp_path, 'r', encoding='utf-8') as f:
            assert f.read() == content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_write_file_with_multiline():
    """Test writing file with multiline content."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        content = "Line 1\nLine 2\nLine 3"
        result = await write_file(tmp_path, content)
        
        assert result == f"Successfully wrote to {tmp_path}"
        
        with open(tmp_path, 'r', encoding='utf-8') as f:
            assert f.read() == content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_write_file_empty_content():
    """Test writing file with empty content."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        content = ""
        result = await write_file(tmp_path, content)
        
        assert result == f"Successfully wrote to {tmp_path}"
        
        with open(tmp_path, 'r', encoding='utf-8') as f:
            assert f.read() == content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_read_file_existing():
    """Test reading an existing file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write("Test content")
    
    try:
        result = await read_file(tmp_path)
        assert result == "Test content"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_read_file_with_unicode():
    """Test reading file with unicode content."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write("你好，世界！")
    
    try:
        result = await read_file(tmp_path)
        assert result == "你好，世界！"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_read_file_with_multiline():
    """Test reading file with multiline content."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write("Line 1\nLine 2\nLine 3")
    
    try:
        result = await read_file(tmp_path)
        assert result == "Line 1\nLine 2\nLine 3"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_read_file_empty():
    """Test reading an empty file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        result = await read_file(tmp_path)
        assert result == ""
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_read_file_not_existing():
    """Test reading a non-existent file."""
    non_existent_path = "/tmp/non_existent_file_12345.txt"
    # Ensure the file doesn't exist
    if os.path.exists(non_existent_path):
        os.remove(non_existent_path)
    
    result = await read_file(non_existent_path)
    assert result == f"Error: The file at {non_existent_path} does not exist."


@pytest.mark.asyncio
async def test_delete_file_existing():
    """Test deleting an existing file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write("Test content")
    
    assert os.path.exists(tmp_path)
    
    result = await delete_file(tmp_path)
    assert result == f"Successfully deleted the file at {tmp_path}"
    assert not os.path.exists(tmp_path)


@pytest.mark.asyncio
async def test_delete_directory_existing():
    """Test deleting an existing directory."""
    tmp_dir = tempfile.mkdtemp()
    
    # Create a file inside the directory
    test_file = os.path.join(tmp_dir, "test.txt")
    with open(test_file, 'w') as f:
        f.write("test")
    
    assert os.path.exists(tmp_dir)
    
    result = await delete_file(tmp_dir)
    assert result == f"Successfully deleted the directory at {tmp_dir} and all its contents"
    assert not os.path.exists(tmp_dir)


@pytest.mark.asyncio
async def test_delete_file_not_existing():
    """Test deleting a non-existent file."""
    non_existent_path = "/tmp/non_existent_file_12345.txt"
    # Ensure the file doesn't exist
    if os.path.exists(non_existent_path):
        os.remove(non_existent_path)
    
    result = await delete_file(non_existent_path)
    assert result == f"Error: The file or directory at {non_existent_path} does not exist."


@pytest.mark.asyncio
async def test_delete_directory_not_existing():
    """Test deleting a non-existent directory."""
    non_existent_dir = "/tmp/non_existent_dir_12345"
    # Ensure the directory doesn't exist
    if os.path.exists(non_existent_dir):
        shutil.rmtree(non_existent_dir)
    
    result = await delete_file(non_existent_dir)
    assert result == f"Error: The file or directory at {non_existent_dir} does not exist."


@pytest.mark.asyncio
async def test_write_read_roundtrip():
    """Test writing and then reading a file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        original_content = "Roundtrip test content\nWith multiple lines"
        
        # Write
        write_result = await write_file(tmp_path, original_content)
        assert "Successfully wrote" in write_result
        
        # Read
        read_result = await read_file(tmp_path)
        assert read_result == original_content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_write_overwrite_read():
    """Test writing, overwriting, and reading a file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        # First write
        await write_file(tmp_path, "First content")
        assert await read_file(tmp_path) == "First content"
        
        # Overwrite
        await write_file(tmp_path, "Second content")
        assert await read_file(tmp_path) == "Second content"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_delete_file_then_read():
    """Test deleting a file and then trying to read it."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write("Test content")
    
    # Delete
    delete_result = await delete_file(tmp_path)
    assert "Successfully deleted" in delete_result
    
    # Try to read (should fail)
    read_result = await read_file(tmp_path)
    assert "Error" in read_result
    assert "does not exist" in read_result
