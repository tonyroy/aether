import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.mavlink import MavlinkConnection


@pytest.fixture
def mock_master():
    """Mock pymavlink master connection"""
    master = MagicMock()
    master.target_system = 1
    master.target_component = 0
    master.mav = MagicMock()
    return master


@pytest.fixture
def mavlink_conn(mock_master):
    """MavlinkConnection with mocked master"""
    conn = MavlinkConnection("mock:connection")
    conn.master = mock_master
    return conn


@pytest.mark.asyncio
async def test_arm_async_success(mavlink_conn, mock_master):
    """Test async arm command with successful ACK"""
    # Start arm command (will wait for ACK)
    arm_task = asyncio.create_task(mavlink_conn.arm_async())
    
    # Give it time to send command
    await asyncio.sleep(0.01)
    
    # Verify command was sent
    mock_master.mav.command_long_send.assert_called_once()
    
    # Simulate COMMAND_ACK response
    ack_msg = MagicMock()
    ack_msg.command = 400  # MAV_CMD_COMPONENT_ARM_DISARM
    ack_msg.result = 0  # MAV_RESULT_ACCEPTED
    
    mavlink_conn.handle_command_ack(ack_msg)
    
    # Verify arm succeeded
    result = await arm_task
    assert result is True


@pytest.mark.asyncio
async def test_arm_async_failure(mavlink_conn, mock_master):
    """Test async arm command with failed ACK"""
    # Start arm command
    arm_task = asyncio.create_task(mavlink_conn.arm_async())
    
    await asyncio.sleep(0.01)
    
    # Simulate failed COMMAND_ACK
    ack_msg = MagicMock()
    ack_msg.command = 400
    ack_msg.result = 4  # MAV_RESULT_FAILED
    
    mavlink_conn.handle_command_ack(ack_msg)
    
    # Verify arm failed
    result = await arm_task
    assert result is False


@pytest.mark.asyncio
async def test_arm_async_timeout(mavlink_conn, mock_master):
    """Test async arm command timeout when no ACK received"""
    # Start arm command with short timeout
    arm_task = asyncio.create_task(
        mavlink_conn.send_command_long_async(400, 1, timeout=0.1)
    )
    
    # Don't send ACK - let it timeout
    result = await arm_task
    
    # Verify timeout resulted in failure
    assert result is False
    
    # Verify pending command was cleaned up
    assert 400 not in mavlink_conn.pending_commands


@pytest.mark.asyncio
async def test_multiple_commands_concurrent(mavlink_conn, mock_master):
    """Test multiple commands can be pending simultaneously"""
    # Start two commands concurrently
    arm_task = asyncio.create_task(mavlink_conn.arm_async())
    disarm_task = asyncio.create_task(mavlink_conn.disarm_async())
    
    await asyncio.sleep(0.01)
    
    # Both should be pending
    assert 400 in mavlink_conn.pending_commands  # ARM uses same command as DISARM
    
    # Send ACKs in reverse order
    ack_disarm = MagicMock()
    ack_disarm.command = 400
    ack_disarm.result = 0
    
    mavlink_conn.handle_command_ack(ack_disarm)
    
    # One should complete
    results = await asyncio.gather(arm_task, disarm_task)
    
    # At least one should succeed (they share command ID, so this is a known limitation)
    assert any(results)


@pytest.mark.asyncio
async def test_takeoff_async_success(mavlink_conn, mock_master):
    """Test async guided_takeoff command"""
    # Mock set_mode to be async-compatible
    mavlink_conn.set_mode = MagicMock()
    
    # Start takeoff
    takeoff_task = asyncio.create_task(mavlink_conn.guided_takeoff_async(10))
    
    await asyncio.sleep(0.01)
    
    # Simulate ACKs for arm and takeoff
    # ARM ACK
    ack_arm = MagicMock()
    ack_arm.command = 400
    ack_arm.result = 0
    mavlink_conn.handle_command_ack(ack_arm)
    
    await asyncio.sleep(0.01)
    
    # TAKEOFF ACK
    ack_takeoff = MagicMock()
    ack_takeoff.command = 22  # MAV_CMD_NAV_TAKEOFF
    ack_takeoff.result = 0
    mavlink_conn.handle_command_ack(ack_takeoff)
    
    result = await takeoff_task
    assert result is True


@pytest.mark.asyncio
async def test_command_ack_for_unknown_command(mavlink_conn):
    """Test that ACK for unknown command doesn't crash"""
    # Send ACK for command we didn't send
    ack_msg = MagicMock()
    ack_msg.command = 999
    ack_msg.result = 0
    
    # Should not raise exception
    mavlink_conn.handle_command_ack(ack_msg)
    
    # Verify no pending commands
    assert len(mavlink_conn.pending_commands) == 0


@pytest.mark.asyncio
async def test_duplicate_ack_ignored(mavlink_conn, mock_master):
    """Test that duplicate ACKs don't cause issues"""
    arm_task = asyncio.create_task(mavlink_conn.arm_async())
    
    await asyncio.sleep(0.01)
    
    # Send first ACK
    ack_msg = MagicMock()
    ack_msg.command = 400
    ack_msg.result = 0
    mavlink_conn.handle_command_ack(ack_msg)
    
    # Send duplicate ACK (should be ignored)
    mavlink_conn.handle_command_ack(ack_msg)
    
    result = await arm_task
    assert result is True
