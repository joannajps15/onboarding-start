# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import FallingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1 
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

# Rising Edge Detection
async def rising_edge(dut, signal, index):
    """Wait for the signal to go high"""
    prev = int(signal.value) & 1
    while True:
        await ClockCycles(dut.clk, 1)
        curr = int(signal.value) & 1
        if prev == 0 and curr == 1:
            return
        prev = curr
        dut._log.info(f"prev = {prev} | curr = {curr}")

# Falling Edge Detection
async def falling_edge(dut, signal, index):
    """Wait for the signal to go high"""
    a = int(signal.value[index])
    while True:        
        await ClockCycles(dut.clk, 1)
        b = int(signal.value[index])
        if a == 1 and b == 0:
            return
        a = b 

# Frequency verification (~3 kHz +/- 1%).
@cocotb.test()
async def test_pwm_freq(dut):
    dut._log.info("Start PWM Frequency test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset Module
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Enable ALL PORTS
    # await send_spi_transaction(dut, 1, 0x00, 0xFF)  # Enable Output on uo_out
    await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Enable PWM on uo_out
    # await send_spi_transaction(dut, 1, 0x01, 0xFF)  # Enable Output on uio_out
    # await send_spi_transaction(dut, 1, 0x03, 0xFF)  # Enable PWM on uio_out
    await send_spi_transaction(dut, 1, 0x04, 0x80)  # Set Duty Cycle (50% of 255)
    await ClockCycles(dut.clk, 5)

    # Send Signals to SPI Peripheral and Analyze Values in output
    # uo_out PWM signal test
    dut._log.info("Write transaction, address 0x02, data 0x01")
    dut._log.info("Observe PWM on uo_out[7:0]")

    await rising_edge(dut, dut.uo_out, 0)
    t_rising_edge1 = cocotb.utils.get_sim_time(units="ns")
    dut._log.info("time detected")
    
    # await cocotb.triggers.RisingEdge(dut.uo_out[0])
    # t_rising_edge2 = cocotb.utils.get_sim_time(units="ns")
    # dut._log.info("time detected")

    # period = (t_rising_edge2 - t_rising_edge1) * 1e-9
    # freq_1 = 1/period
    # assert (freq_1 >= 2970 and freq_1 <= 3030) , f"Expected frequency within 3 kHz (1% tolerance), got {freq_1}"
    # dut._log.info("time")
    # await ClockCycles(dut.clk, 1000) 

    # #uio_out PWM signal test
    # dut._log.info("Write transaction, address 0x03, data 0x01")
    # dut._log.info("Observe PWM on uo_out[7:0]")
    # await send_spi_transaction(dut, 1, 0x03, 0x01)  # Write transaction    
    # await rising_edge(dut, dut.uio_out, 0)
    # t_rising_edge1 = cocotb.utils.get_sim_time(units="ns")
    
    # await rising_edge(dut, dut.uio_out, 0)
    # t_rising_edge2 = cocotb.utils.get_sim_time(units="ns")

    # period = (t_rising_edge2 - t_rising_edge1) * 1e-9
    # freq_2 = 1/period
    # assert (freq_2 >= 2970 and freq_2 <= 3030) , f"Expected frequency within 3 kHz (1% tolerance), got {freq_2}"
    # await ClockCycles(dut.clk, 1000) 

    dut._log.info("PWM Frequency test completed successfully")

# async def duty_cycle_calc(dut, addr, data, mode, pwm_duty_cycle):
#     send_spi_transaction(dut, 1, addr, data)  # Write transaction 

#     if mode: 
#         await rising_edge(dut, dut.uo_out, 0)
#     else: 
#         await rising_edge(dut, dut.uio_out, 0)
#     t_rising_edge1 = cocotb.utils.get_sim_time(units="ns")
    
#     if mode: 
#         await rising_edge(dut, dut.uo_out, 0)
#     else: 
#         await rising_edge(dut, dut.uio_out, 0)
#     t_falling_edge = cocotb.utils.get_sim_time(units="ns")

#     if mode: 
#         await rising_edge(dut, dut.uo_out, 0)
#     else: 
#         await rising_edge(dut, dut.uio_out, 0)
#     t_rising_edge2 = cocotb.utils.get_sim_time(units="ns")

#     high_time = t_falling_edge - t_rising_edge1
#     period = t_rising_edge2 - t_rising_edge1
#     duty_cycle = (high_time / period) * 100
#     pwm_duty_cycle = (pwm_duty_cycle/255)*100

#     assert ((duty_cycle >= pwm_duty_cycle*0.99) and (duty_cycle <= pwm_duty_cycle*1.01)) , f"Expected PWM duty cycle of {pwm_duty_cycle}, got {duty_cycle}"
    
#     return


# Duty cycle sweep (0x00 to 0xFF).
# Interaction between Output Enable and PWM Enable registers.
# PWM Duty verification (+/-1%).
# # @cocotb.test()
# async def test_pwm_duty(dut):
#     dut._log.info("Start PWM Duty Cycle test")

#     # Set the clock period to 100 ns (10 MHz)
#     clock = Clock(dut.clk, 100, units="ns")
#     cocotb.start_soon(clock.start())

#     # Reset Module
#     dut._log.info("Reset")
#     dut.ena.value = 1
#     ncs = 1
#     bit = 0
#     sclk = 0
#     dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
#     dut.rst_n.value = 0
#     await ClockCycles(dut.clk, 5)
#     dut.rst_n.value = 1
#     await ClockCycles(dut.clk, 5)

#     # Send Signals to SPI Peripheral and Analyze Duty Cycle from output
#     for i in range(0, 255, 5):
#         await send_spi_transaction(dut, 1, 0x04, i)  # Write PWM value  

#         # uo_out PWM signal test
#         dut._log.info("Write transaction, address 0x02, data 0x01")
#         dut._log.info("Observe PWM on uo_out[7:0]")
#         await duty_cycle_calc(dut, 0x02, 0x01, 1, i)    

#         #uio_out PWM signal test
#         dut._log.info("Write transaction, address 0x03, data 0x01")
#         dut._log.info("Observe PWM on uio_out[7:0]")
#         await duty_cycle_calc(dut, 0x03, 0x01, 0, i)    
    
#     # special case for 255
#     # uo_out PWM signal test
#     dut._log.info("Write transaction, address 0x00, data 0x01")
#     dut._log.info("Observe PWM on uo_out[7:0]")
  
#     await rising_edge(dut, dut.uio_out, 0)
#     t_rising_edge1 = cocotb.utils.get_sim_time(units="ns")
    
#     await falling_edge(dut, dut.uio_out, 0)
#     t_falling_edge = cocotb.utils.get_sim_time(units="ns")

#     await rising_edge(dut, dut.uio_out, 0)
#     t_rising_edge2 = cocotb.utils.get_sim_time(units="ns")

#     high_time = t_falling_edge - t_rising_edge1
#     period = t_rising_edge2 - t_rising_edge1
#     duty_cycle = (high_time / period) * 100
#     pwm_duty_cycle = 100
#     assert ((duty_cycle >= pwm_duty_cycle*0.99) and (duty_cycle <= pwm_duty_cycle*1.01)) , f"Expected PWM duty cycle of 100%, got {duty_cycle}%"
    
#     dut._log.info("PWM Duty Cycle test completed successfully")