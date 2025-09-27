/*
 * Copyright (c) 2024 Joanna Sebastiampillai
 * SPDX-License-Identifier: Apache-2.0
 */

// STEPS TO DEBUG

// all bit-widths are correctly declared
// negedge rst_n might not be supported?
// width mismatches

`default_nettype none

module spi_peripheral (
    input wire clk, //peripheral clock
    input wire rst_n,
    input wire sclk, //serial clock
    input wire ncs, //active-low chip-select
    input wire copi, //controller out, peripheral in
    output reg [7:0] en_reg_out_7_0,
    output reg [7:0] en_reg_out_15_8,
    output reg [7:0] en_reg_pwm_7_0,
    output reg [7:0] en_reg_pwm_15_8,
    output reg [7:0] pwm_duty_cycle
);

    // SIGNAL SYNCHRONIZATION
    reg [2:0] r_sclk;
    reg [1:0] r_ncs;
    reg [1:0] r_copi;

    always @ (posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_sclk[2:0] <= 3'b000;
            r_ncs[1:0] <= 2'b00;
            r_copi[1:0] <= 2'b00;
        end else begin
            //STAGE ONE
            r_sclk[0] <= sclk;
            r_ncs[0] <= ncs;
            r_copi[0] <= copi;

            //STAGE TWO
            r_sclk[1] <= r_sclk[0];
            r_ncs[1] <= r_ncs[0];
            r_copi[1] <= r_copi[0];

            //STAGE THREE
            r_sclk[2] <= r_sclk[1];
        end
    end

    localparam max_address = 7'h04;
    reg [4:0] count; //(3) BIT COUNTING
    reg [15:0] temp; //data temp
    wire high = ~r_sclk[2] & r_sclk[1];
    wire low = r_sclk[2] & ~r_sclk[1];
    reg count_enable;

    // CAPTURE 16-BITS
    always @ (posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            //reset signals
            count_enable <= 1;
            count <= 0;
            temp <= 0;      
            
            en_reg_out_7_0 <= 0;
            en_reg_out_15_8 <= 0;
            en_reg_pwm_7_0 <= 0;
            en_reg_pwm_15_8 <= 0;
            pwm_duty_cycle <= 0;    
        end else if (~r_ncs[1]) begin
            //get values
            if (count_enable && high) begin
                temp[15-count] <= r_copi[1];
                count <= count + 1;
                count_enable <= 0;
            end else if (low) begin
                count_enable <= 1;
            end
        end else if ((count == 5'd16) && (temp[15] == 1) && (temp[14:8] <= max_address)) begin
                case (temp[14:8])
                    7'h00: en_reg_out_7_0 <= temp[7:0];
                    7'h01: en_reg_out_15_8 <= temp[7:0];
                    7'h02: en_reg_pwm_7_0 <= temp[7:0];
                    7'h03: en_reg_pwm_15_8 <= temp[7:0];
                    7'h04: pwm_duty_cycle <= temp[7:0];
                    default: ;
                endcase                
                //finished processing: reset signals            
                count_enable <= 1;
                temp <= 0;
                count <= 0;
        end else begin
            //reset signals
            count_enable <= 1;
            temp <= 0;
            count <= 0;
        end 
    end

endmodule