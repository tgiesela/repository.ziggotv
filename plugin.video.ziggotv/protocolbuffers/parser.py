import io
from enum import Enum


class ProtoType(Enum):
    VARINT = 0
    I64 = 1
    LEN = 2
    SGROUP = 3
    EGROUP = 4
    I32 = 5


class ElementKind(Enum):
    NOTSET = 0
    PRIMITIVE = 1,
    GROUP = 2,
    PRIMITIVE_OR_GROUP = 3


def settype(type: ProtoType, fieldnumber: int):
    (fieldnumber << 3) | ProtoType


def gettype(b):
    prototype = b[0] & 0x07
    return prototype


class ProtoElement:
    def __init__(self):
        self.length_FT = 0
        self.length_LEN = 0
        self.length = 0
        self.field_number = 0
        self.prototype = None
        self.element_kind = ElementKind.NOTSET
        self.data = bytearray()
        self.subelements = {}
        self.max_length = 0
        self.parent = None

    def __decode_varint(self, _bytes: bytearray):
        # _bytes must have been parsed by _extract_varint
        _decodedbytes = bytearray(len(_bytes))
        _varint = 0
        _i = 0
        _int = _bytes[_i]
        _decodedbytes[_i] = _int & 0x007f
        while _i < len(_bytes) - 1:
            _i = _i + 1
            _int = _bytes[_i]
            _decodedbytes[_i] = _int & 0x007f

        # swap the bytes
        _i = 0
        _swapped = bytearray(len(_decodedbytes))
        while _i < len(_decodedbytes):
            _swapped[len(_decodedbytes) - (_i + 1)] = _decodedbytes[_i]
            _i += 1

        for _i in range(len(_bytes)):
            _varint = (_varint << 7) + (_swapped[_i] & 0x7f)

        return _varint

    def __decode_fixedint(self, _bytes: bytearray):
        # _bytes must have been parsed by _extract_varint
        _decodedbytes = bytearray(len(_bytes))
        _varint = 0
        _i = 0
        _decodedbytes[_i] =  _bytes[_i]
        while _i < len(_bytes) - 1:
            _i = _i + 1
            _decodedbytes[_i] = _bytes[_i]

        # swap the bytes
        _i = 0
        _swapped = bytearray(len(_decodedbytes))
        while _i < len(_decodedbytes):
            _swapped[len(_decodedbytes) - (_i + 1)] = _decodedbytes[_i]
            _i += 1

        for _i in range(len(_bytes)):
            _varint = (_varint << 8) + (_swapped[_i])

        return _varint
    def __extract_varint(self, f):
        # length of varint determined by msb, as long as this is on, a next byte will follow
        _rawdata = bytearray(10)
        _i = 0
        _rawdata[_i] = int.from_bytes(f.read(1), byteorder='little')
        _int = _rawdata[_i]
        _bytes_processed = 1
        _bit_set = _int >> 7
        while _bit_set:
            _i = _i + 1
            _rawdata[_i] = int.from_bytes(f.read(1), byteorder='little')
            _int = _rawdata[_i]
            _bytes_processed += 1
            _bit_set = _int >> 7

        return _bytes_processed, _rawdata

    def get_int(self):
        if self.prototype == ProtoType.VARINT:
            return self.__decode_varint(self.data[0:self.length])
        else:
            return self.__decode_fixedint(self.data[0:self.length])

    def __store_len(self, f):
        self.length_LEN, _bytes = self.__extract_varint(f)
        self.length = self.__decode_varint(_bytes[0:self.length_LEN])
        if self.length > self.max_length:
            raise RuntimeError("length exceeds max_length")
        self.data = bytearray(self.length)
        self.data = f.read(self.length)

    def __store_group(self, f):
        self.data = bytearray(self.length)
        self.data = f.read(self.length)

    def decode_fieldnr_and_type(self, f):
        self.length_FT, _bytes = self.__extract_varint(f)
        _val = self.__decode_varint(_bytes[0:self.length_FT])
        self.prototype = ProtoType(_val & 0x0007)
        self.field_number = _val >> 3

    def decode(self, f):
        self.decode_fieldnr_and_type(f)
        if self.prototype == ProtoType.I32:
            self.length = 4
            self.data = f.read(4)
            self.element_kind = ElementKind.PRIMITIVE
        elif self.prototype == ProtoType.I64:
            self.length = 8
            self.data = f.read(8)
            self.element_kind = ElementKind.PRIMITIVE
        elif self.prototype == ProtoType.VARINT:
            self.length, self.data = self.__extract_varint(f)
            self.element_kind = ElementKind.PRIMITIVE
        elif ProtoType.LEN:
            self.__store_len(f)
            self.element_kind = ElementKind.PRIMITIVE_OR_GROUP
        else:
            self.__store_group(f)
            self.element_kind = ElementKind.GROUP

    def encode_varint(self, val):
        # val to bytes 7 bits in each byte
        _bytenr = 0
        _valbytes = bytearray(1)
        _byteval = val & 0x7f
        _valbytes[0] = _byteval
        val = val >> 7
        while val > 0:
            _valbytes[_bytenr] = _valbytes[_bytenr] | 0x80
            _bytenr += 1
            _byteval = val & 0x7f
            _valbytes.extend(_byteval.to_bytes())
            _valbytes[_bytenr] = _byteval
            val = val >> 7
        return _valbytes

    def encode_fixedint(self, _len, _val):
        _valbytes = bytearray(_len)
        for _i in range(_len):
            _valbytes[_i] = self.data[_i]
        return _valbytes

    def get_TF(self):
        tag = (self.field_number << 3) + self.prototype.value
        return self.encode_varint(tag)

    def get_length(self, _len):
        return self.encode_varint(_len)

    def build(self):
        _msg = bytearray()
        if self.element_kind == ElementKind.GROUP:
            for _element in self.subelements.values():
                _msg.extend(_element.build())
        else:
            _msg = self.data
        _full_msg = bytearray()
        _full_msg.extend(self.get_TF())
        if self.prototype == ProtoType.VARINT:
            # There is no length field
            _full_msg.extend(self.encode_varint(self.get_int()))
        elif self.prototype == ProtoType.I32:
            _full_msg.extend(self.encode_fixedint(4, self.get_fixedint()))
        elif self.prototype == ProtoType.I64:
            _full_msg.extend(self.encode_fixedint(8, self.get_fixedint()))
        else:
            _full_msg.extend((self.get_length(len(_msg))))
            _full_msg.extend(_msg)
        return _full_msg


class ProtoParser:
    def __init__(self):
        self.__tag_dict = None
        self.inputlength = None

    def _parse_tag_info(self, f, maxlength):
        _element = ProtoElement()
        _element.max_length = maxlength
        _element.decode(f)
        return _element

    def _parse_msg(self, f, input_length):
        if input_length <= 0:
            raise RuntimeError("Nothing to process")
        _bytes_processed = 0
        _item = 1
        _dict_for_level = {}
        while _bytes_processed < input_length:
            _element = self._parse_tag_info(f, input_length - _bytes_processed)
            _dict_for_level[_item] = _element
            _bytes_processed += _element.length_LEN + _element.length + _element.length_FT
            if _bytes_processed > input_length or _element.length > input_length:
                raise RuntimeError("Insufficient data")
            if ElementKind(_element.element_kind) == ElementKind.GROUP:
                _element.subelements = self._parse_msg(io.BytesIO(_element.data), _element.length)
                for el in _element.subelements.values():
                    el.parent = _element
            elif ElementKind(_element.element_kind) == ElementKind.PRIMITIVE_OR_GROUP:
                try:
                    _element.subelements = self._parse_msg(io.BytesIO(_element.data), _element.length)
                    if _element.subelements is not None:
                        _element.element_kind = ElementKind.GROUP
                        for el in _element.subelements.values():
                            el.parent = _element
                    else:
                        _element.element_kind = ElementKind.PRIMITIVE
                except:
                    pass
            # else:
            #    return None

            _item += 1
        return _dict_for_level

    def do_parse(self, buf):
        f = io.BytesIO(buf)
        f.seek(0, 2)
        self.inputlength = f.tell()
        f.seek(0, 0)
        self.__tag_dict = self._parse_msg(f, self.inputlength)
        return self.__tag_dict

    def do_build(self):
        _msg = bytearray()
        for element in self.__tag_dict.values():
            _msg.extend(element.build())
        return _msg

    def find_element(self, id) -> ProtoElement | None:
        """
        Finds an element in the parsed elements, returns null if not found
        :param id: string in the form "1.3.2."
        :return: element
        """
        fieldnumbers = id.split('.')
        eldict = self.__tag_dict
        i = 0
        while i < len(fieldnumbers) and eldict is not None:
            nr = fieldnumbers[i]
            foundel = None
            for tag in eldict.values():
                if tag.field_number == int(nr):
                    foundel = tag
                    break
            if foundel is not None:
                eldict = foundel.subelements
                i += 1
            else:
                eldict = None
        if i < len(fieldnumbers):
            return None
        return foundel

    def set_tags(self, _widevinetags):
        self.__tag_dict = _widevinetags

    def new_element(self, param):
        el = ProtoElement()
        el.field_number = param
        return el

    def add_tag(self, parent_tag, child):
        max_key = -1
        found = False
        key = None
        for tag in parent_tag.subelements:
            if tag > max_key:
                max_key = tag
            el = parent_tag.subelements[tag]
            if el.field_number == child.field_number:
                print("Replacing tag with fieldnumber: ", child.field_number)
                key = tag
                found = True
        child.parent = parent_tag
        if found:
            parent_tag.subelements.update({key: child})
        else:
            parent_tag.subelements.update({max_key+1: child})

    def get_tags(self):
        return self.__tag_dict


def print_tag(element):
    paragraph = str(element.field_number) + "."
    parent = element.parent
    while parent is not None:
        paragraph = str(parent.field_number) + "." + paragraph
        parent = parent.parent
    indent = ' ' * len(paragraph)

    if element.prototype in [ProtoType.I32, ProtoType.I64, ProtoType.VARINT]:
        print(paragraph + " val: {0}".format(element.get_int()))
    else:
        print(paragraph + " val: {0}".format(element.data[0:element.length]))
    print(indent + " hex: {0}".format(element.data[0:element.length].hex()))
    print(indent + " length: {0}".format(element.length))


def print_tags(tags):
    element: ProtoElement
    for tag in tags:
        element = tags[tag]
        if ElementKind(element.element_kind) == ElementKind.GROUP:
            # print(tabs + "{0}.".format(element.field_number))
            print_tags(element.subelements)
        else:
            print_tag(element)


if __name__ == '__main__':
    parser = ProtoParser()
    tags = parser.do_parse(bytes.fromhex("0a0378797a10d20918959aef3a"))
    print_tags(tags)
    newbytes = parser.do_build()
    print(newbytes.hex())
    print("------Widevine certificate")
    widevincert = bytes.fromhex(
        "0ac502080312101dc8b0e73f05ea9a9e786dbf6540fd01189389ada405228e023082010a0282010100c192abebaa94fed6a476cb5b6f5"
        "f23b77d1650f9d39ed6e1580d984ecfb5793c0b0a88ba51cf477f3fae42747d834cb38fc0acbe7feb08661c0cfd8c0d193f4a5a6e3f24"
        "85961b8da3f21e7c5c9c89663979fd9e5d6e94bf718ef48721744a141d0e0abf07d706997769acf8ce31227559b9b3e9ecf7bc44f4992"
        "559a2ed3ff0b9eb95c301f2af4602fb7de3fe2cf4b8ce1deaf9e1bb85baf79f13809a00d285a5f8ebffb4c60a1873b3e9d1940165c8bf"
        "4cfd315da646b95c78da33f3093a33345104676edbda8a2aaa314be04e6c5a83f7b3131170029567754dbbe2aea269fd3c909316135d7"
        "3f6a0fd7e8949f6b0fc4586d989a2717cca0eed17f7aefc5f02030100013a18616c63617472617a5f746573745f64726d5f7365727665"
        "7212800325134ee22264a7f39d9a623c93637c2bd9b4776ce10c2d138283937260e03e2fc9e1c901f0824063c4cb0d1e2992911fabbb0"
        "f6fde3ca6ed0297162ede589c3726442fb45cab91806977d9a57148118b4d2706d4ae0bd3056619f62525cb3d2dd0a9db60ebe184595e"
        "0669081b2b88cd409c237dd82dd503c80620e06f1635fb1769b920d9cca3f0d02f6ff61805d764a171334292c0fab3444e9b84152e3e3"
        "4bb45ea15cc4a1faac900a72a2a6795eba07373a7998054b52f4ce3c562f25dcc6f682ca04ca64fc16b3b1ec853a5322f1b4697a16af0"
        "0bdd76234e03b33c125cc9113a068b4b3f1868be3aea64d2ba01025bf26bc0caed50e814fe538e1238a4df89cfe45454c47e30d92eb69"
        "0ec892af3e8930e3e3f8794c0a506bc585c4483725609b64802ac63eb61da63b98f8248327f69c098236c5b57f0dc9d352a2fe1ad01be"
        "310b56b3060de196a63ee0c3f4ee9ec89bb1fda102d2021b4ab8911bc7ab883ce75e67e3b3af53d74f402524e6bfd62ba3c7d983ad8b7"
        "9722de9838136")
    widevinetags = parser.do_parse(widevincert)
    print_tags(widevinetags)
    parser.find_element("1.2")
    newbytes = parser.do_build()
    print(newbytes.hex())
    print('--------------License request in firefox-------------------')
    licenserequest = bytes.fromhex(
        '080112890c0aa30b080112850a0ac30208021210909534de468313fd8c6e242d76f9f4a21891edcca206228c0130818902818100fbf59efd9777b7d05b6e9e0ab04003f19a317efb4fb3af109077f36e84e53643e333b00206d6537a0c426f2b1d63598466ef9ad5d5a555df0be857480e0f9bdd492fc2507e519f684e164714f1d2fb84ba04a37e071fd7cfd5ae322b59e61964b7dbab3f75ccb28d481b25a216070948bb04335d1319d620a201b910532b1f7d020301000128aee40148015a91010a8c0130818902818100cc0e84a24662fbe3756bcdc59c6eb45b42e1f5960ff0ea2ce1e854467409f58ed2f42eb4c64bf8f838cd1993d889f58adcc449410313934b077ce79de39b528259e0eda22834dd97fc1f467ff8466eb9e88f823ec53c5abe65fdc47567e6c37b0c9fc1ea5dc454889f8bec55e27d217ed797f286976da9d34baf12135b62176702030100011001128002e0883176e8c37f9fbcab98ddfe3ea27326589b9e096d459f3e4cb74e65539ea9f60f748098a5ce467055dd714afcb5cb45560309eee087a1ad63d1eaa1f56a35fe47115298e877bbb58f72b851d00062c11f6879f952f7bd642f72f93a1d8d4a73df6f1c255111e2856e9c14c0bceb401b20338fb1d126dc49fc23a8b9e4dde2d36c0037c44f2470abe78b3e10de708bc1d1b691f0b96aa3f37ed43c431fbaf1eb392be6f3c6e72668a1cf5b21d1f7bef905d67dd291b9064c9da025bade40f7d28a1827694cad62ce663f7885f3cc92533a23076fd3a439cb75bcb38548b1317646c8d86ee91ae1a64c98f9fc82b17fb232e0ad2faed9bbf7ab026d55b9cb6b1ab7050ab10208011210051467ae42984d1e949867eb66b348e718b7f3aea006228e023082010a0282010100e35bb74ba94e7eebbded4e7f218840f6bbcfdbf380deb75c9448ec3faf0dfd03d7bfcddb65eb5d0903411a0ceb0b79adf860802d5422dcdde474beb264bd27f5eb227455fad101405e78b15f063e30478b6ec32c6fb1a8f4b183c52cffe47183b0d7b739e96e53a66627fe94ca6443b82656ba377c05d3cee37f06a889032e496dfadfa19e30c4f9439439f46ae524a328cfeb5cfff9a11d070c68a2702d90f5d3e61f14ebfe60e1a07a6cc7db31c08474f7f5d0e1c8e87677aebba28959732c1250e8275e5c2ca1ba3809dfd277cd7bbdb614cd2f8ca2d56d1089104d272557eda00b36de9f6396a77ed99b4266c0e323bdbd569082b385683e059bd0b53ee5020301000128aee4014801128003586906063100d4e43a2cd7aea8307631eb4cf14a07640ff9a93e56ee6d8f96273104be8a5bfa0e6c1f3df295773a9852e0bff2afc3eb74173242ca9c5d2f97cc4a0d2434c32851795c5dfc31c8e33941281845f061b47084ff0b273139ae0d7a0d1d8ab2f7a9cac65ad62fedce280d1660fce2336684da5ab2266822c1ea2cb539def8f0781d6c9af16f0c1d09caecb4c583ee022682239d5ad9623d4f418585ec38f9564de7383981b0f7ede716f4364470e408159e59430695b2a6a29c5ee99a9a7f1b612a13ce7e215e2f8667002d6b09d87cdf0fc951d79f279e014b31d65573d9a0355fbedab4193b0b2ba2502080865c1efd41c205cf67797d86a63c356863cc87553f12894a32aae4804ab9d66b48f622d4db20751bb6cac25e8aec0f304736dc5170d1b376f4d8096a1d9038e1973c4ae440eafde0f2bf3477bd561ed7ab8922f8bf75018a0ffc2634e9bb2fa3ca6d9db3f9ac5ee7a55bb5c669899a65c99644b6e1e64e03f4ab64dbb2bfbbb005537b7d8e6c8ccd0f9923771785bf20021a1b0a116172636869746563747572655f6e616d6512067838362d36341a160a0c636f6d70616e795f6e616d651206476f6f676c651a170a0a6d6f64656c5f6e616d6512094368726f6d6543444d1a180a0d706c6174666f726d5f6e616d65120757696e646f77731a230a147769646576696e655f63646d5f76657273696f6e120b342e31302e323636322e33320a0800100018012001281012440a420a2c0801121090e32a4712f5480bab7abc8a4fef25da22146e6c5f74765f7374616e64616172645f63656e63380010011a10a1be4307066f1ea94d81565dc8d30f33180120f483dfa80630163897f996b3054a0b342e31302e323636322e331a8001af26567a00197eafcdc860e18d0fe2494680336a6d60e363eb4544a14906655ce39af184c1cda03fc1fffa4e2ccfc478871295731a63566b0c868a958d6835e3af097e4d96079c0ca4ea3e4333267be377cfc37bd9641e1fae211688386bfee751c95938aa7965ab7a2181daa339a289a0bebedf96b0bbd292db4793ea2c5cba4a140000000100000014000500105665bc97c66e7b50'
    )
    tags = parser.do_parse(licenserequest)
    print_tags(tags)

    print('--------------License request Kodi-------------------')
    licenserequestkodi = bytes.fromhex(
        '080112890c0aa30b080112850a0ac30208021210909534de468313fd8c6e242d76f9f4a21891edcca206228c0130818902818100fbf59efd9777b7d05b6e9e0ab04003f19a317efb4fb3af109077f36e84e53643e333b00206d6537a0c426f2b1d63598466ef9ad5d5a555df0be857480e0f9bdd492fc2507e519f684e164714f1d2fb84ba04a37e071fd7cfd5ae322b59e61964b7dbab3f75ccb28d481b25a216070948bb04335d1319d620a201b910532b1f7d020301000128aee40148015a91010a8c0130818902818100cc0e84a24662fbe3756bcdc59c6eb45b42e1f5960ff0ea2ce1e854467409f58ed2f42eb4c64bf8f838cd1993d889f58adcc449410313934b077ce79de39b528259e0eda22834dd97fc1f467ff8466eb9e88f823ec53c5abe65fdc47567e6c37b0c9fc1ea5dc454889f8bec55e27d217ed797f286976da9d34baf12135b62176702030100011001128002e0883176e8c37f9fbcab98ddfe3ea27326589b9e096d459f3e4cb74e65539ea9f60f748098a5ce467055dd714afcb5cb45560309eee087a1ad63d1eaa1f56a35fe47115298e877bbb58f72b851d00062c11f6879f952f7bd642f72f93a1d8d4a73df6f1c255111e2856e9c14c0bceb401b20338fb1d126dc49fc23a8b9e4dde2d36c0037c44f2470abe78b3e10de708bc1d1b691f0b96aa3f37ed43c431fbaf1eb392be6f3c6e72668a1cf5b21d1f7bef905d67dd291b9064c9da025bade40f7d28a1827694cad62ce663f7885f3cc92533a23076fd3a439cb75bcb38548b1317646c8d86ee91ae1a64c98f9fc82b17fb232e0ad2faed9bbf7ab026d55b9cb6b1ab7050ab10208011210051467ae42984d1e949867eb66b348e718b7f3aea006228e023082010a0282010100e35bb74ba94e7eebbded4e7f218840f6bbcfdbf380deb75c9448ec3faf0dfd03d7bfcddb65eb5d0903411a0ceb0b79adf860802d5422dcdde474beb264bd27f5eb227455fad101405e78b15f063e30478b6ec32c6fb1a8f4b183c52cffe47183b0d7b739e96e53a66627fe94ca6443b82656ba377c05d3cee37f06a889032e496dfadfa19e30c4f9439439f46ae524a328cfeb5cfff9a11d070c68a2702d90f5d3e61f14ebfe60e1a07a6cc7db31c08474f7f5d0e1c8e87677aebba28959732c1250e8275e5c2ca1ba3809dfd277cd7bbdb614cd2f8ca2d56d1089104d272557eda00b36de9f6396a77ed99b4266c0e323bdbd569082b385683e059bd0b53ee5020301000128aee4014801128003586906063100d4e43a2cd7aea8307631eb4cf14a07640ff9a93e56ee6d8f96273104be8a5bfa0e6c1f3df295773a9852e0bff2afc3eb74173242ca9c5d2f97cc4a0d2434c32851795c5dfc31c8e33941281845f061b47084ff0b273139ae0d7a0d1d8ab2f7a9cac65ad62fedce280d1660fce2336684da5ab2266822c1ea2cb539def8f0781d6c9af16f0c1d09caecb4c583ee022682239d5ad9623d4f418585ec38f9564de7383981b0f7ede716f4364470e408159e59430695b2a6a29c5ee99a9a7f1b612a13ce7e215e2f8667002d6b09d87cdf0fc951d79f279e014b31d65573d9a0355fbedab4193b0b2ba2502080865c1efd41c205cf67797d86a63c356863cc87553f12894a32aae4804ab9d66b48f622d4db20751bb6cac25e8aec0f304736dc5170d1b376f4d8096a1d9038e1973c4ae440eafde0f2bf3477bd561ed7ab8922f8bf75018a0ffc2634e9bb2fa3ca6d9db3f9ac5ee7a55bb5c669899a65c99644b6e1e64e03f4ab64dbb2bfbbb005537b7d8e6c8ccd0f9923771785bf20021a1b0a116172636869746563747572655f6e616d6512067838362d36341a160a0c636f6d70616e795f6e616d651206476f6f676c651a170a0a6d6f64656c5f6e616d6512094368726f6d6543444d1a180a0d706c6174666f726d5f6e616d65120757696e646f77731a230a147769646576696e655f63646d5f76657273696f6e120b342e31302e323636322e33320a0800100018012001281012440a420a2c0801121090e32a4712f5480bab7abc8a4fef25da22146e6c5f74765f7374616e64616172645f63656e63380010011a10a1be4307066f1ea94d81565dc8d30f33180120f483dfa80630163897f996b3054a0b342e31302e323636322e331a8001af26567a00197eafcdc860e18d0fe2494680336a6d60e363eb4544a14906655ce39af184c1cda03fc1fffa4e2ccfc478871295731a63566b0c868a958d6835e3af097e4d96079c0ca4ea3e4333267be377cfc37bd9641e1fae211688386bfee751c95938aa7965ab7a2181daa339a289a0bebedf96b0bbd292db4793ea2c5cba4a140000000100000014000500105665bc97c66e7b50'
    )
    koditags = parser.do_parse(licenserequestkodi)
    print_tags(koditags)

    print('-----------Modify Licence request Kodi ---------------')
    parser.set_tags(widevinetags)
    tag17 = parser.find_element("1.7")
    tag12 = parser.find_element("1.2")

    parser.set_tags(koditags)
    tag2 = parser.find_element("2")
    tag28 = parser.find_element("2.8")
    if tag28 is None:
        tag28 = parser.new_element(8)
        tag28.element_kind = ElementKind.GROUP
        parser.add_tag(tag2, tag28)
    tag281 = tag17
    tag281.field_number = 1
    parser.add_tag(tag28, tag281)
    tag282 = tag12
    tag282.field_number = 2
    parser.add_tag(tag28, tag282)
    print_tags({2: tag28})
    print_tags(parser.get_tags())
