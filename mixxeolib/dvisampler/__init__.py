from migen.fhdl.std import *
from migen.bank.description import AutoCSR

from mixxeolib.dvisampler.edid import EDID
from mixxeolib.dvisampler.clocking import Clocking
from mixxeolib.dvisampler.datacapture import DataCapture
from mixxeolib.dvisampler.charsync import CharSync
from mixxeolib.dvisampler.wer import WER
from mixxeolib.dvisampler.decoding import Decoding
from mixxeolib.dvisampler.chansync import ChanSync
from mixxeolib.dvisampler.analysis import SyncPolarity, ResolutionDetection, FrameExtraction
from mixxeolib.dvisampler.dma import DMA

class DVISampler(Module, AutoCSR):
	def __init__(self, pads, lasmim, n_dma_slots=2):
		self.submodules.edid = EDID(pads)
		self.submodules.clocking = Clocking(pads)

		for datan in range(3):
			name = "data" + str(datan)

			cap = DataCapture(getattr(pads, name + "_p"), getattr(pads, name + "_n"), 8)
			setattr(self.submodules, name + "_cap", cap)
			self.comb += cap.serdesstrobe.eq(self.clocking.serdesstrobe)

			charsync = CharSync()
			setattr(self.submodules, name + "_charsync", charsync)
			self.comb += charsync.raw_data.eq(cap.d)

			wer = WER()
			setattr(self.submodules, name + "_wer", wer)
			self.comb += wer.data.eq(charsync.data)

			decoding = Decoding()
			setattr(self.submodules, name + "_decod", decoding)
			self.comb += [
				decoding.valid_i.eq(charsync.synced),
				decoding.input.eq(charsync.data)
			]

		self.submodules.chansync = ChanSync()
		self.comb += [
			self.chansync.valid_i.eq(self.data0_decod.valid_o & \
			  self.data1_decod.valid_o & self.data2_decod.valid_o),
			self.chansync.data_in0.eq(self.data0_decod.output),
			self.chansync.data_in1.eq(self.data1_decod.output),
			self.chansync.data_in2.eq(self.data2_decod.output),
		]

		self.submodules.syncpol = SyncPolarity()
		self.comb += [
			self.syncpol.valid_i.eq(self.chansync.chan_synced),
			self.syncpol.data_in0.eq(self.chansync.data_out0),
			self.syncpol.data_in1.eq(self.chansync.data_out1),
			self.syncpol.data_in2.eq(self.chansync.data_out2)
		]

		self.submodules.resdetection = ResolutionDetection()
		self.comb += [
			self.resdetection.valid_i.eq(self.syncpol.valid_o),
			self.resdetection.de.eq(self.syncpol.de),
			self.resdetection.vsync.eq(self.syncpol.vsync)
		]

		self.submodules.frame = FrameExtraction(24*lasmim.dw//32)
		self.comb += [
			self.frame.valid_i.eq(self.syncpol.valid_o),
			self.frame.de.eq(self.syncpol.de),
			self.frame.vsync.eq(self.syncpol.vsync),
			self.frame.r.eq(self.syncpol.r),
			self.frame.g.eq(self.syncpol.g),
			self.frame.b.eq(self.syncpol.b)
		]

		self.submodules.dma = DMA(lasmim, n_dma_slots)
		self.comb += self.frame.frame.connect(self.dma.frame)
		self.ev = self.dma.ev

	autocsr_exclude = {"ev"}
