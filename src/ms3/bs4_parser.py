"""
.. |act_dur| replace:: :ref:`act_dur <act_dur>`
.. |alt_label| replace:: :ref:`alt_label <alt_label>`
.. |added_tones| replace:: :ref:`added_tones <chord_tones>`
.. |articulation| replace:: :ref:`articulation <articulation>`
.. |bass_note| replace:: :ref:`bass_note <bass_note>`
.. |barline| replace:: :ref:`barline <barline>`
.. |breaks| replace:: :ref:`breaks <breaks>`
.. |cadence| replace:: :ref:`cadence <cadence>`
.. |changes| replace:: :ref:`changes <changes>`
.. |chord| replace:: :ref:`chord <chord>`
.. |chord_id| replace:: :ref:`chord_id <chord_id>`
.. |chord_tones| replace:: :ref:`chord_tones <chord_tones>`
.. |chord_type| replace:: :ref:`chord_type <chord_type>`
.. |crescendo_hairpin| replace:: :ref:`crescendo_hairpin <hairpins>`
.. |crescendo_line| replace:: :ref:`crescendo_line <cresc_lines>`
.. |decrescendo_hairpin| replace:: :ref:`decrescendo_hairpin <hairpins>`
.. |diminuendo_line| replace:: :ref:`diminuendo_line <cresc_lines>`
.. |dont_count| replace:: :ref:`dont_count <dont_count>`
.. |duration| replace:: :ref:`duration <duration>`
.. |duration_qb| replace:: :ref:`duration_qb <duration_qb>`
.. |dynamics| replace:: :ref:`dynamics <dynamics>`
.. |figbass| replace:: :ref:`figbass <figbass>`
.. |form| replace:: :ref:`form <form>`
.. |globalkey| replace:: :ref:`globalkey <globalkey>`
.. |globalkey_is_minor| replace:: :ref:`globalkey_is_minor <globalkey_is_minor>`
.. |gracenote| replace:: :ref:`gracenote <gracenote>`
.. |harmony_layer| replace:: :ref:`harmony_layer <harmony_layer>`
.. |keysig| replace:: :ref:`keysig <keysig>`
.. |label| replace:: :ref:`label <label>`
.. |label_type| replace:: :ref:`label_type <label_type>`
.. |localkey| replace:: :ref:`localkey <localkey>`
.. |localkey_is_minor| replace:: :ref:`localkey_is_minor <localkey_is_minor>`
.. |lyrics:1| replace:: :ref:`lyrics:1 <lyrics_1>`
.. |mc| replace:: :ref:`mc <mc>`
.. |mc_offset| replace:: :ref:`mc_offset <mc_offset>`
.. |mc_onset| replace:: :ref:`mc_onset <mc_onset>`
.. |midi| replace:: :ref:`midi <midi>`
.. |mn| replace:: :ref:`mn <mn>`
.. |mn_onset| replace:: :ref:`mn_onset <mn_onset>`
.. |next| replace:: :ref:`next <next>`
.. |nominal_duration| replace:: :ref:`nominal_duration <nominal_duration>`
.. |numbering_offset| replace:: :ref:`numbering_offset <numbering_offset>`
.. |numeral| replace:: :ref:`numeral <numeral>`
.. |offset_x| replace:: :ref:`offset_x <offset>`
.. |offset_y| replace:: :ref:`offset_y <offset>`
.. |Ottava:15mb| replace:: :ref:`Ottava:15mb <ottava>`
.. |Ottava:8va| replace:: :ref:`Ottava:8va <ottava>`
.. |Ottava:8vb| replace:: :ref:`Ottava:8vb <ottava>`
.. |pedal| replace:: :ref:`pedal <pedal>`
.. |phraseend| replace:: :ref:`phraseend <phraseend>`
.. |qpm| replace:: :ref:`qpm <qpm>`
.. |quarterbeats| replace:: :ref:`quarterbeats <quarterbeats>`
.. |quarterbeats_all_endings| replace:: :ref:`quarterbeats_all_endings <quarterbeats_all_endings>`
.. |relativeroot| replace:: :ref:`relativeroot <relativeroot>`
.. |regex_match| replace:: :ref:`regex_match <regex_match>`
.. |repeats| replace:: :ref:`repeats <repeats>`
.. |root| replace:: :ref:`root <root>`
.. |scalar| replace:: :ref:`scalar <scalar>`
.. |slur| replace:: :ref:`slur <slur>`
.. |staff| replace:: :ref:`staff <staff>`
.. |staff_text| replace:: :ref:`staff_text <staff_text>`
.. |system_text| replace:: :ref:`system_text <system_text>`
.. |tempo| replace:: :ref:`tempo <tempo>`
.. |TextLine| replace:: :ref:`TextLine <textline>`
.. |tied| replace:: :ref:`tied <tied>`
.. |timesig| replace:: :ref:`timesig <timesig>`
.. |tpc| replace:: :ref:`tpc <tpc>`
.. |tremolo| replace:: :ref:`tremolo <tremolo>`
.. |volta| replace:: :ref:`volta <volta>`
.. |voice| replace:: :ref:`voice <voice>`
"""

import re, sys
import logging
from fractions import Fraction as frac
from collections import defaultdict, ChainMap # for merging dictionaries
from typing import Literal

import bs4  # python -m pip install beautifulsoup4 lxml
import pandas as pd
import numpy as np

from .annotations import Annotations
from .bs4_measures import MeasureList
from .logger import function_logger, LoggedClass, temporarily_suppress_warnings
from .transformations import add_quarterbeats_col
from .utils import adjacency_groups, assert_dfs_equal, color2rgba, color_params2rgba, column_order, fifths2name, FORM_DETECTION_REGEX, \
    get_quarterbeats_length, make_continuous_offset_dict, ordinal_suffix, pretty_dict, resolve_dir, rgba2attrs, rgba2params, rgb_tuple2format, sort_note_list



class _MSCX_bs4(LoggedClass):
    """ This sister class implements :py:class:`~.score.MSCX`'s methods for a score parsed with beautifulsoup4.

    Attributes
    ----------
    mscx_src : :obj:`str`
        Path to the uncompressed MuseScore 3 file (MSCX) to be parsed.

    """

    durations = {"measure": frac(1),
                 "breve": frac(2),  # in theory, of course, they could have length 1.5
                 "long": frac(4),   # and 3 as well and other values yet
                 "whole": frac(1),
                 "half": frac(1 / 2),
                 "quarter": frac(1 / 4),
                 "eighth": frac(1 / 8),
                 "16th": frac(1 / 16),
                 "32nd": frac(1 / 32),
                 "64th": frac(1 / 64),
                 "128th": frac(1 / 128),
                 "256th": frac(1 / 256),
                 "512th": frac(1 / 512),
                 "1024th": frac(1 / 1024)}

    def __init__(self, mscx_src, read_only=False, logger_cfg={}):
        """

        Parameters
        ----------
        mscx_src
        read_only
        logger_cfg : :obj:`dict`, optional
            The following options are available:
            'name': LOGGER_NAME -> by default the logger name is based on the parsed file(s)
            'level': {'W', 'D', 'I', 'E', 'C', 'WARNING', 'DEBUG', 'INFO', 'ERROR', 'CRITICAL'}
            'file': PATH_TO_LOGFILE to store all log messages under the given path.
        """
        super().__init__(subclass='_MSCX_bs4', logger_cfg=logger_cfg)
        self.soup = None
        self.metadata = None
        self._metatags = None
        self._measures, self._events, self._notes = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        self.mscx_src = mscx_src
        self.read_only = read_only
        self.first_mc = 1
        self.measure_nodes = {}
        """{staff -> {MC -> tag} }"""

        self.tags = {}  # only used if not self.read_only
        """{MC -> {staff -> {voice -> tag} } }"""

        self.has_annotations = False
        self.n_form_labels = 0
        self._ml = None
        cols = ['mc', 'mc_onset', 'duration', 'staff', 'voice', 'scalar', 'nominal_duration']
        self._nl, self._cl, self._rl, self._nrl, self._fl = pd.DataFrame(), pd.DataFrame(columns=cols), pd.DataFrame(columns=cols), \
                                                            pd.DataFrame(columns=cols), pd.DataFrame(columns=cols)
        self._style = None

        self.parse_measures()



    def parse_mscx(self):
        """ Load the XML structure from the score in self.mscx_src and store references to staves and measures.
        """
        assert self.mscx_src is not None, "No MSCX file specified." \
                                          ""
        with open(self.mscx_src, 'r', encoding='utf-8') as file:
            self.soup = bs4.BeautifulSoup(file.read(), 'xml')

        if self.version[0] != '3':
            # self.logger.exception(f"Cannot parse MuseScore {self.version} file.")
            raise ValueError(f"""Cannot parse MuseScore {self.version} file.
Use 'ms3 convert' command or pass parameter 'ms' to Score to temporally convert.""")

        # Populate measure_nodes with one {mc: <Measure>} dictionary per staff.
        # The <Staff> nodes containing the music are siblings of <Part>
        # <Part> contains <Staff> nodes with staff information which is being ignored for now
        for staff in self.soup.find('Part').find_next_siblings('Staff'):
            staff_id = int(staff['id'])
            self.measure_nodes[staff_id] = {}
            for mc, measure in enumerate(staff.find_all('Measure'), start=self.first_mc):
                self.measure_nodes[staff_id][mc] = measure


    def parse_measures(self):
        """ Converts the score into the three DataFrame self._measures, self._events, and self._notes
        """
        if self.soup is None:
            self.parse_mscx()
        grace_tags = ['grace4', 'grace4after', 'grace8', 'grace8after', 'grace16', 'grace16after', 'grace32',
                      'grace32after', 'grace64', 'grace64after', 'appoggiatura', 'acciaccatura']

        measure_list, event_list, note_list = [], [], []
        staff_ids = tuple(self.measure_nodes.keys())
        chord_id = 0
        # For every measure: bundle the <Measure> nodes from every staff
        for mc, measure_stack in enumerate(
                zip(
                    *[[measure_node for measure_node in measure_dict.values()] for measure_dict in
                      self.measure_nodes.values()]
                ),
                start=self.first_mc):
            if not self.read_only:
                self.tags[mc] = {}
            # iterate through staves and collect information about each <Measure> node
            for staff_id, measure in zip(staff_ids, measure_stack):
                if not self.read_only:
                    self.tags[mc][staff_id] = {}
                measure_info = {'mc': mc, 'staff': staff_id}
                measure_info.update(recurse_node(measure, exclude_children=['voice']))
                # iterate through <voice> tags and run a position counter
                voice_nodes = measure.find_all('voice', recursive=False)
                # measure_info['voices'] = len(voice_nodes)
                for voice_id, voice_node in enumerate(voice_nodes, start=1):
                    if not self.read_only:
                        self.tags[mc][staff_id][voice_id] = defaultdict(list)
                    current_position = frac(0)
                    duration_multiplier = 1
                    multiplier_stack = [1]
                    tremolo_type = None
                    tremolo_component = 0
                    # iterate through children of <voice> which constitute the note level of one notational layer
                    for event_node in voice_node.find_all(recursive=False):
                        event_name = event_node.name

                        event = {
                            'mc': mc,
                            'staff': staff_id,
                            'voice': voice_id,
                            'mc_onset': current_position,
                            'duration': frac(0)}

                        if event_name == 'Chord':
                            event['chord_id'] = chord_id
                            grace = event_node.find(grace_tags)


                            dur, dot_multiplier = bs4_chord_duration(event_node, duration_multiplier)
                            if grace:
                                event['gracenote'] = grace.name
                            else:
                                event['duration'] = dur
                            chord_info = dict(event)

                            tremolo_tag = event_node.find('Tremolo')
                            if tremolo_tag:
                                if tremolo_component > 0:
                                    raise NotImplementedError("Chord with <Tremolo> follows another one with <Tremolo>")
                                tremolo_type = tremolo_tag.subtype.string
                                tremolo_duration_node = event_node.find('duration')
                                if tremolo_duration_node:
                                    # the tremolo has two components that factually start sounding
                                    # on the same onset, but are encoded as two subsequent <Chord> tags
                                    tremolo_duration = tremolo_duration_node.string
                                    tremolo_component = 1
                                else:
                                    # the tremolo consists of one <Chord> only
                                    tremolo_duration = dur
                            elif tremolo_component == 1:
                                tremolo_component = 2
                            if tremolo_type:
                                chord_info['tremolo'] = f"{tremolo_duration}_{tremolo_type}_{tremolo_component}"
                                if tremolo_component in (0, 2):
                                    tremolo_type = None
                                if tremolo_component == 2:
                                    duration_to_complete_tremolo = event_node.find(
                                        'duration').string
                                    assert duration_to_complete_tremolo == tremolo_duration, "Two components of tremolo have non-matching <duration>"
                                    tremolo_component = 0

                            for chord_child in event_node.find_all(recursive=False):
                                if chord_child.name == 'Note':
                                    note_event = dict(chord_info, **recurse_node(chord_child, prepend=chord_child.name))
                                    note_list.append(note_event)
                                else:
                                    event.update(recurse_node(chord_child, prepend='Chord/' + chord_child.name))
                            chord_id += 1
                        elif event_name == 'Rest':
                            event['duration'], dot_multiplier = bs4_rest_duration(event_node, duration_multiplier)
                        elif event_name == 'location':  # <location> tags move the position counter
                            event['duration'] = frac(event_node.fractions.string)
                        elif event_name == 'Tuplet':
                            multiplier_stack.append(duration_multiplier)
                            duration_multiplier = duration_multiplier * frac(int(event_node.normalNotes.string),
                                                                             int(event_node.actualNotes.string))
                        elif event_name == 'endTuplet':
                            duration_multiplier = multiplier_stack.pop()

                        # These nodes describe the entire measure and go into measure_list
                        # All others go into event_list
                        if event_name in ['TimeSig', 'KeySig', 'BarLine'] or (
                                event_name == 'Spanner' and 'type' in event_node.attrs and event_node.attrs[
                            'type'] == 'Volta'):
                            measure_info.update(recurse_node(event_node, prepend=f"voice/{event_name}"))
                        else:
                            event.update({'event': event_name})
                            if event_name == 'Chord':
                                event['scalar'] = duration_multiplier * dot_multiplier
                                for attr, value in event_node.attrs.items():
                                    event[f"Chord:{attr}"] = value
                            elif event_name == 'Rest':
                                event['scalar'] = duration_multiplier * dot_multiplier
                                event.update(recurse_node(event_node, prepend=event_name))
                            else:
                                event.update(recurse_node(event_node, prepend=event_name))
                            event_list.append(event)

                        if not self.read_only:
                            remember = {'name': event_name,
                                        'duration': event['duration'],
                                        'tag': event_node, }
                            position = event['mc_onset']
                            if event_name == 'location' and event['duration'] < 0:
                                # this is a backwards pointer: store it where it points to for easy deletion
                                position += event['duration']
                            self.tags[mc][staff_id][voice_id][position].append(remember)

                        if tremolo_component != 1:
                            # In case a tremolo appears in the score as two subsequent events of equal length,
                            # MuseScore assigns a <duration> of half the note value to both components of a tremolo.
                            # The parser, instead, assigns the actual note value and the same position to both the
                            # <Chord> with the <Tremolo> tag and the following one. In other words, the current_position
                            # pointer is moved forward in all cases except for the first component of a tremolo
                            current_position += event['duration']

                measure_list.append(measure_info)
        self._measures = column_order(pd.DataFrame(measure_list))
        self._events = column_order(pd.DataFrame(event_list))
        if 'chord_id' in self._events.columns:
            self._events.chord_id = self._events.chord_id.astype('Int64')
        self._notes = column_order(pd.DataFrame(note_list))
        if len(self._events) == 0:
            self.logger.warning("Empty score?")
        else:
            self.has_annotations = 'Harmony' in self._events.event.values
            if 'StaffText/text' in self._events.columns:
                form_labels = self._events['StaffText/text'].str.contains(FORM_DETECTION_REGEX).fillna(False)
                if form_labels.any():
                    self.n_form_labels = sum(form_labels)
        self.update_metadata()




    def output_mscx(self, filepath):
        try:
            mscx_string = bs4_to_mscx(self.soup)
        except:
            self.logger.error(f"Couldn't output MSCX because of the following error:\n{sys.exc_info()[1]}")
            return False
        with open(resolve_dir(filepath), 'w', encoding='utf-8') as file:
            file.write(mscx_string)
        self.logger.info(f"Score written to {filepath}.")
        return True

    def update_metadata(self):
        self.metadata = self._get_metadata()

    def _make_measure_list(self, sections=True, secure=True, reset_index=True):
        """ Regenerate the measure list from the parsed score with advanced options."""
        logger_cfg = self.logger_cfg.copy()
        return MeasureList(self._measures, sections=sections, secure=secure, reset_index=reset_index, logger_cfg=logger_cfg)



    def chords(self, mode: Literal['auto','strict','all'] = 'auto', interval_index: bool = False) -> pd.DataFrame:
        """ DataFrame of :ref:`chords` representing all <Chord> tags contained in the MuseScore file
        (all <note> tags come within one) and attached score information and performance maerks, e.g.
        lyrics, dynamics, articulations, slurs (see the explanation for the ``mode`` parameter for more details).
        Comes with the columns |quarterbeats|, |duration_qb|, |mc|, |mn|, |mc_onset|, |mn_onset|, |timesig|, |staff|,
        |voice|, |duration|, |gracenote|, |tremolo|, |nominal_duration|, |scalar|, |volta|, |chord_id|, |dynamics|,
        |articulation|, |staff_text|, |slur|, |Ottava:8va|, |Ottava:8vb|, |pedal|, |TextLine|, |decrescendo_hairpin|,
        |diminuendo_line|, |crescendo_line|, |crescendo_hairpin|, |tempo|, |qpm|, |lyrics:1|, |Ottava:15mb|

        Args:
            mode:
                Defaults to 'auto', meaning that additional performance markers available in the score are to be included,
                namely lyrics, dynamics, fermatas, articulations, slurs, staff_text, system_text, tempo, and spanners
                (e.g. slurs, 8va lines, pedal lines). This results in NaN values in the column 'chord_id' for those
                markers that are not part of a <Chord> tag, e.g. <Dynamic>, <StaffText>, or <Tempo>. To prevent that, pass
                'strict', meaning that only <Chords> are included, i.e. the column 'chord_id' will have no empty values.
                Set to 'all' for 'auto' behaviour, but additionally creating empty columns even for those performance
                markers not occurring in the score.
            interval_index:  Pass True to replace the default :obj:`~pandas.RangeIndex` by an :obj:`~pandas.IntervalIndex`.

        Returns:
            DataFrame of :ref:`chords` representing all <Chord> tags contained in the MuseScore file.
        """
        if mode == 'strict':
            chords = self.cl()
        else:
            chords = self.get_chords(mode=mode)
        chords = add_quarterbeats_col(chords, self.offset_dict(), interval_index=interval_index)
        return chords


    def cl(self, recompute: bool = False) -> pd.DataFrame:
        """Get the raw :ref:`chords` without adding quarterbeat columns."""
        if recompute or len(self._cl) == 0:
            self._cl = self.get_chords(mode='strict')
        return self._cl.copy()


    def events(self, interval_index: bool = False) -> pd.DataFrame:
        """ DataFrame representing a raw skeleton of the score's XML structure and contains all :ref:`events`
        contained in it. It is the original tabular representation of the MuseScore file’s source code from which
        all other tables, except ``measures`` are generated.

        Args:
            interval_index: Pass True to replace the default :obj:`~pandas.RangeIndex` by an :obj:`~pandas.IntervalIndex`.

        Returns:
            DataFrame containing the original tabular representation of all :ref:`events` encoded in the MuseScore file.
        """
        events = column_order(self.add_standard_cols(self._events))
        events = add_quarterbeats_col(events, self.offset_dict(), interval_index=interval_index)
        return events


    def form_labels(self, detection_regex: str = None, interval_index: bool = False) -> pd.DataFrame:
        """ DataFrame representing :ref:`form labels <form_labels>` (or other) that have been encoded as <StaffText>s rather than in the <Harmony> layer.
        This function essentially filters all StaffTexts matching the ``detection_regex`` and adds the standard position columns.

        Args:
            detection_regex:
                By default, detects all labels starting with one or two digits followed by a column
                (see :const:`the regex <~.utils.FORM_DETECTION_REGEX>`). Pass another regex to retrieve only StaffTexts matching this one.
            interval_index: Pass True to replace the default :obj:`~pandas.RangeIndex` by an :obj:`~pandas.IntervalIndex`.

        Returns:
            DataFrame containing all StaffTexts matching the ``detection_regex``
        """
        form = self.fl(detection_regex=detection_regex)
        if form is None:
            return
        form = add_quarterbeats_col(form, self.offset_dict(), interval_index=interval_index)
        return form

    def fl(self, detection_regex: str = None) -> pd.DataFrame:
        """ Get the raw :ref:`form_labels` (or other) that match the ``detection_regex``, but without adding quarterbeat columns.

        Args:
            detection_regex:
                By default, detects all labels starting with one or two digits followed by a column
                (see :const:`the regex <~.utils.FORM_DETECTION_REGEX>`). Pass another regex to retrieve only StaffTexts matching this one.

        Returns:
            DataFrame containing all StaffTexts matching the ``detection_regex`` or None
        """
        if 'StaffText/text' in self._events.columns:
            if detection_regex is None:
                detection_regex = FORM_DETECTION_REGEX
            is_form_label = self._events['StaffText/text'].str.contains(FORM_DETECTION_REGEX).fillna(False)
            if is_form_label.sum() == 0:
                return
            form_labels = self._events[is_form_label].rename(columns={'StaffText/text': 'form_label'})
            cols = ['mc', 'mc_onset', 'mn', 'mn_onset', 'staff', 'voice', 'timesig', 'volta', 'form_label']
            self._fl = self.add_standard_cols(form_labels)[cols].sort_values(['mc', 'mc_onset'])
            return self._fl
        return

    def measures(self, interval_index: bool = False) -> pd.DataFrame:
        """ DataFrame representing the :ref:`measures` of the MuseScore file (which can be incomplete measures). Comes with
        the columns |mc|, |mn|, |quarterbeats|, |duration_qb|, |keysig|, |timesig|, |act_dur|, |mc_offset|, |volta|, |numbering_offset|, |dont_count|, |barline|, |breaks|,
        |repeats|, |next|

        Args:
            interval_index: Pass True to replace the default :obj:`~pandas.RangeIndex` by an :obj:`~pandas.IntervalIndex`.

        Returns:
            DataFrame representing the :ref:`measures <measures>` of the MuseScore file (which can be incomplete measures).
        """
        measures = self.ml()
        duration_qb = (measures.act_dur * 4).astype(float)
        measures.insert(2, "duration_qb", duration_qb)
        # add quarterbeats column
        # functionality adapted from utils.make_continuous_offset()
        filter_voltas = measures.volta.notna().any()
        qb_column_name = "quarterbeats_all_endings" if filter_voltas else "quarterbeats"
        quarterbeats_col = (measures.act_dur.cumsum() * 4).shift(fill_value=0)
        measures.insert(2, qb_column_name, quarterbeats_col)
        if filter_voltas:
            self.logger.debug(f"No quarterbeats are assigned to first endings. Pass unfold=True to "
                         f"compute quarterbeats for a full playthrough.")
            if 3 in measures.volta.values:
                self.logger.info(
                    f"Piece contains third endings, note that only second endings are taken into account.")
            quarterbeats_col = measures.loc[measures.volta.fillna(2) == 2, 'act_dur']\
                .cumsum()\
                .shift(fill_value=0)\
                .reindex(measures.index)
            measures.insert(2, "quarterbeats", quarterbeats_col * 4)
        return measures.copy()

    @property
    def metatags(self):
        if self._metatags is None:
            if self.soup is None:
                self.make_writeable()
            self._metatags = Metatags(self.soup)
        return self._metatags

    def ml(self, recompute: bool = False) -> pd.DataFrame:
        """ Get the raw :ref:`measures` without adding quarterbeat columns.

        Args:
            recompute: By default, the measures are cached. Pass True to enforce recomputing anew.
        """
        if recompute or self._ml is None:
            self._ml = self._make_measure_list()
        return self._ml.ml.copy()

    def notes(self, interval_index: bool = False) -> pd.DataFrame:
        """ DataFrame representing the :ref:`notes` of the MuseScore file. Comes with the columns
        |quarterbeats|, |duration_qb|, |mc|, |mn|, |mc_onset|, |mn_onset|, |timesig|, |staff|, |voice|, |duration|, |gracenote|, |tremolo|, |nominal_duration|, |scalar|, |tied|,
        |tpc|, |midi|, |volta|, |chord_id|


        Args:
            interval_index: Pass True to replace the default :obj:`~pandas.RangeIndex` by an :obj:`~pandas.IntervalIndex`.

        Returns:
            DataFrame representing the :ref:`notes` of the MuseScore file.
        """
        notes = self.nl()
        notes = add_quarterbeats_col(notes, self.offset_dict(), interval_index=interval_index)
        return notes

    def nl(self, recompute: bool = False) -> pd.DataFrame:
        """ Get the raw :ref:`notes` without adding quarterbeat columns.

        Args:
            recompute:  By default, the measures are cached. Pass True to enforce recomputing anew.
        """
        if recompute or len(self._nl) == 0:
            self.make_standard_notelist()
        return self._nl

    def notes_and_rests(self, interval_index : bool = False) -> pd.DataFrame:
        """ DataFrame representing the :ref:`notes_and_rests` of the MuseScore file. Comes with the columns
        |quarterbeats|, |duration_qb|, |mc|, |mn|, |mc_onset|, |mn_onset|, |timesig|, |staff|, |voice|, |duration|,
        |gracenote|, |tremolo|, |nominal_duration|, |scalar|, |tied|, |tpc|, |midi|, |volta|, |chord_id|

        Args:
            interval_index: Pass True to replace the default :obj:`~pandas.RangeIndex` by an :obj:`~pandas.IntervalIndex`.

        Returns:
            DataFrame representing the :ref:`notes_and_rests` of the MuseScore file.
        """
        nrl = self.nrl()
        nrl = add_quarterbeats_col(nrl, self.offset_dict(), interval_index=interval_index)
        return nrl

    def nrl(self, recompute: bool = False) -> pd.DataFrame:
        """Get the raw :ref:`notes_and_rests` without adding quarterbeat columns.

        Args:
            recompute:  By default, the measures are cached. Pass True to enforce recomputing anew.
        """
        if recompute or len(self._nrl) == 0:
            nr = pd.concat([self.nl(), self.rl()]).astype({col: 'Int64' for col in ['tied', 'tpc', 'midi', 'chord_id']})
            self._nrl = sort_note_list(nr.reset_index(drop=True))
        return self._nrl

    def offset_dict(self, all_endings: bool = False) -> dict:
        """

        Args:
            all_endings:

        Returns:

        """
        measures = self.measures().set_index('mc')
        if all_endings and 'quarterbeats_all_endings' in measures.columns:
            col = 'quarterbeats_all_endings'
        else:
            col = 'quarterbeats'
        offset_dict = measures[col].to_dict()
        last_row = measures.iloc[-1]
        offset_dict['end'] = last_row[col] + 4 * last_row.act_dur
        return offset_dict

    def rests(self, interval_index : bool = False) -> pd.DataFrame:
        """ DataFrame representing the :ref:`rests` of the MuseScore file. Comes with the columns
        |quarterbeats|, |duration_qb|, |mc|, |mn|, |mc_onset|, |mn_onset|, |timesig|, |staff|, |voice|, |duration|,
        |nominal_duration|, |scalar|, |volta|

        Args:
            interval_index: Pass True to replace the default :obj:`~pandas.RangeIndex` by an :obj:`~pandas.IntervalIndex`.

        Returns:
            DataFrame representing the :ref:`rests` of the MuseScore file.
        """
        rests = self.rl()
        rests = add_quarterbeats_col(rests, self.offset_dict(), interval_index=interval_index)
        return rests

    def rl(self, recompute: bool = False) -> pd.DataFrame:
        """Get the raw :ref:`rests` without adding quarterbeat columns.

        Args:
            recompute:  By default, the measures are cached. Pass True to enforce recomputing anew.
        """
        if recompute or len(self._rl) == 0:
            self.make_standard_restlist()
        return self._rl

    @property
    def staff_ids(self):
        return list(self.measure_nodes.keys())

    @property
    def style(self):
        if self._style is None:
            if self.soup is None:
                self.make_writeable()
            self._style = Style(self.soup)
        return self._style


    @property
    def volta_structure(self):
        if self._ml is not None:
            return self._ml.volta_structure


    def make_standard_chordlist(self):
        """ Stores the result of self.get_chords(mode='strict')"""
        self._cl = self.get_chords(mode='strict')



    def make_standard_restlist(self):
        self._rl = self.add_standard_cols(self._events[self._events.event == 'Rest'])
        if len(self._rl) == 0:
             return
        self._rl = self._rl.rename(columns={'Rest/durationType': 'nominal_duration'})
        self._rl.loc[:, 'nominal_duration'] = self._rl.nominal_duration.map(self.durations)  # replace string values by fractions
        cols = ['mc', 'mn', 'mc_onset', 'mn_onset', 'timesig', 'staff', 'voice', 'duration', 'nominal_duration', 'scalar', 'volta']
        self._rl = self._rl[cols].reset_index(drop=True)


    def make_standard_notelist(self):
        cols = {'midi': 'Note/pitch',
                'tpc': 'Note/tpc',
                }
        nl_cols = ['mc', 'mn', 'mc_onset', 'mn_onset', 'timesig', 'staff', 'voice', 'duration', 'gracenote', 'nominal_duration',
                   'scalar', 'tied', 'tpc', 'midi', 'volta', 'chord_id']
        if len(self._notes.index) == 0:
            self._nl = pd.DataFrame(columns=nl_cols)
            return
        if 'tremolo' in self._notes.columns:
            nl_cols.insert(9, 'tremolo')
        self._nl = self.add_standard_cols(self._notes)
        self._nl.rename(columns={v: k for k, v in cols.items()}, inplace=True)
        self._nl.loc[:, ['midi', 'tpc']] = self._nl[['midi', 'tpc']].apply(pd.to_numeric).astype('Int64')
        self._nl.tpc -= 14
        self._nl = self._nl.merge(self.cl()[['chord_id', 'nominal_duration', 'scalar']], on='chord_id')
        tie_cols = ['Note/Spanner:type', 'Note/Spanner/next/location', 'Note/Spanner/prev/location']
        self._nl['tied'] = make_tied_col(self._notes, *tie_cols)

        final_cols = [col for col in nl_cols if col in self._nl.columns]
        self._nl = sort_note_list(self._nl[final_cols])



    def get_chords(self, staff=None, voice=None, mode='auto', lyrics=False, dynamics=False, articulation=False,
                   staff_text=False, system_text=False, tempo=False, spanners=False, **kwargs):
        """ Shortcut for ``MSCX.parsed.get_chords()``.
        Retrieve a customized chord lists, e.g. one including less of the processed features or additional,
        unprocessed ones.

        Parameters
        ----------
        staff : :obj:`int`
            Get information from a particular staff only (1 = upper staff)
        voice : :obj:`int`
            Get information from a particular voice only (1 = only the first layer of every staff)
        mode : {'auto', 'all', 'strict'}, optional
            | Defaults to 'auto', meaning that those aspects are automatically included that occur in the score; the resulting
              DataFrame has no empty columns except for those parameters that are set to True.
            | 'all': Columns for all aspects are created, even if they don't occur in the score (e.g. lyrics).
            | 'strict': Create columns for exactly those parameters that are set to True, regardless which aspects occur in the score.
        lyrics : :obj:`bool`, optional
            Include lyrics.
        dynamics : :obj:`bool`, optional
            Include dynamic markings such as f or p.
        articulation : :obj:`bool`, optional
            Include articulation such as arpeggios.
        spanners : :obj:`bool`, optional
            Include spanners such as slurs, 8va lines, pedal lines etc.
        staff_text : :obj:`bool`, optional
            Include expression text such as 'dolce' and free-hand staff text such as 'div.'.
        system_text : :obj:`bool`, optional
            Include system text such as movement titles.
        tempo : :obj:`bool`, optional
            Include tempo markings.
        **kwargs : :obj:`bool`, optional
            Set a particular keyword to True in order to include all columns from the _events DataFrame
            whose names include that keyword. Column names include the tag names from the MSCX source code.

        Returns
        -------
        :obj:`pandas.DataFrame`
            DataFrame representing all <Chord> tags in the score with the selected features.
        """
        cols = {'nominal_duration': 'Chord/durationType',
                'lyrics': 'Chord/Lyrics/text',
                'syllabic': 'Chord/Lyrics/syllabic',
                'verses' : 'Chord/Lyrics/no',
                'articulation': 'Chord/Articulation/subtype',
                'dynamics': 'Dynamic/subtype',
                'system_text': 'SystemText/text',
                'tremolo': 'Chord/Tremolo/subtype'}
        main_cols = ['mc', 'mn', 'mc_onset', 'mn_onset', 'timesig', 'staff', 'voice', 'duration', 'gracenote',
                     'tremolo', 'nominal_duration', 'scalar', 'volta', 'chord_id']
        sel = self._events.event == 'Chord'
        aspects = ['lyrics', 'dynamics', 'articulation', 'staff_text', 'system_text', 'tempo', 'spanners']
        if mode == 'all':
            params = {p: True for p in aspects}
        else:
            l = locals()
            params = {p: l[p] for p in aspects}
        # map parameter to values to select from the event table's 'event' column
        param2event = {
            'dynamics': 'Dynamic',
            'spanners': 'Spanner',
            'staff_text': 'StaffText',
            'system_text': 'SystemText',
            'tempo': 'Tempo'
        }
        selectors = {param: self._events.event == event_name for param, event_name in param2event.items()}
        if mode == 'auto':
            for param, selector in selectors.items():
                if not params[param] and selector.any():
                    params[param] = True
        for param, selector in selectors.items():
            if params[param]:
                sel |= selector
        if staff:
            sel &= self._events.staff == staff
        if voice:
            sel &=  self._events.voice == voice
        df = self.add_standard_cols(self._events[sel])
        if 'chord_id' in df.columns:
            df = df.astype({'chord_id': 'Int64' if df.chord_id.isna().any() else int})
        df.rename(columns={v: k for k, v in cols.items() if v in df.columns}, inplace=True)

        if mode == 'auto':
            if 'lyrics' in df.columns:
                params['lyrics'] = True
            if 'articulation' in df.columns:
                params['articulation'] = True
            if any(c in df.columns for c in ('Spanner:type', 'Chord/Spanner:type')):
                params['spanners'] = True
        if 'nominal_duration' in df.columns:
            df.loc[:, 'nominal_duration'] = df.nominal_duration.map(self.durations) # replace string values by fractions
        new_cols = {}
        if params['lyrics']:
            if 'verses' in df.columns:
                verses = pd.to_numeric(df.verses).astype('Int64')
                verses.loc[df.lyrics.notna()] = verses[df.lyrics.notna()].fillna(0)
                verses += 1
                n_verses = verses.max()
                if n_verses > 1:
                    self.logger.warning(f"Detected lyrics with {n_verses} verses. Unfortunately, only the last "
                                   f"one (for each chord) can currently be extracted.")
                verse_range = range(1, n_verses + 1)
                lyr_cols = [f"lyrics:{verse}" for verse in verse_range]
                columns = [df.lyrics.where(verses == verse, pd.NA).rename(col_name) for verse, col_name in enumerate(lyr_cols, 1)]
            else:
                lyr_cols = ['lyrics:1']
                columns = [df.lyrics.rename('lyrics:1')] if 'lyrics' in df.columns else []
            main_cols.extend(lyr_cols)
            if 'syllabic' in df.columns:
                # turn the 'syllabic' column into the typical dashs
                empty = pd.Series(index=df.index)
                for col in columns:
                    syl_start, syl_mid, syl_end = [empty.where(col.isna() | (df.syllabic != which), '-').fillna('')
                                                   for which in ['begin', 'middle', 'end']]
                    col = syl_end + syl_mid + col + syl_mid + syl_start
            df = pd.concat([df] + columns, axis=1)
        if params['dynamics']:
            main_cols.append('dynamics')
        if params['articulation']:
            main_cols.append('articulation')
        if params['staff_text']:
            main_cols.append('staff_text')
            text_cols = ['StaffText/text', 'StaffText/text/b', 'StaffText/text/i']
            existing_cols = [c for c in text_cols if c in df.columns]
            if len(existing_cols) > 0:
                new_cols['staff_text'] = df[existing_cols].fillna('').sum(axis=1).replace('', pd.NA)
        if params['system_text']:
            main_cols.append('system_text')
        if params['tempo']:
            main_cols.extend(['tempo', 'qpm'])
            text_cols = ['Tempo/text', 'Tempo/text/b', 'Tempo/text/i']
            existing_cols = [c for c in text_cols if c in df.columns]
            tempo_text = df[existing_cols].apply(lambda S: S.str.replace(r"(/ |& )", '', regex=True)).fillna('').sum(axis=1).replace('', pd.NA)
            if 'Tempo/text/sym' in df.columns:
                replace_symbols = defaultdict(lambda: '')
                replace_symbols.update({'metNoteHalfUp': '𝅗𝅥',
                                        'metNoteQuarterUp': '𝅘𝅥',
                                        'metNote8thUp': '𝅘𝅥𝅮',
                                        'metAugmentationDot': '.'})
                symbols = df['Tempo/text/sym'].str.split(expand=True)\
                                              .apply(lambda S: S.str.strip()\
                                              .map(replace_symbols))\
                                              .sum(axis=1)
                tempo_text = symbols + tempo_text
            new_cols['tempo'] = tempo_text
            new_cols['qpm'] = (df['Tempo/tempo'].astype(float) * 60).round().astype('Int64')
        for col in main_cols:
            if (col not in df.columns) and (col not in new_cols):
                new_cols[col] = pd.Series(index=df.index, dtype='object')
        df = pd.concat([df, pd.DataFrame(new_cols)], axis=1)
        additional_cols = []
        if params['spanners']:
            spanner_ids = make_spanner_cols(df, logger=self.logger)
            if len(spanner_ids.columns) > 0:
                additional_cols.extend(spanner_ids.columns.to_list())
                df = pd.concat([df, spanner_ids], axis=1)
        for feature in kwargs.keys():
            additional_cols.extend([c for c in df.columns if feature in c and c not in main_cols])
        return df[main_cols + additional_cols]



    def get_raw_labels(self):
        """ Returns a list of <harmony> tags from the parsed score.

        Returns
        -------
        :obj:`pandas.DataFrame`

        """
        cols = {'harmony_layer': 'Harmony/harmonyType',
                'label': 'Harmony/name',
                'nashville': 'Harmony/function',
                'absolute_root': 'Harmony/root',
                'absolute_base': 'Harmony/base',
                'leftParen': 'Harmony/leftParen',
                'rightParen': 'Harmony/rightParen',
                'offset_x': 'Harmony/offset:x',
                'offset_y': 'Harmony/offset:y',
                'color_r': 'Harmony/color:r',
                'color_g': 'Harmony/color:g',
                'color_b': 'Harmony/color:b',
                'color_a': 'Harmony/color:a'}
        std_cols = ['mc', 'mn', 'mc_onset', 'mn_onset', 'timesig', 'staff', 'voice', 'label',]
        main_cols = std_cols + Annotations.additional_cols
        sel = self._events.event == 'Harmony'
        df = self.add_standard_cols(self._events[sel]).dropna(axis=1, how='all')
        if len(df.index) == 0:
            return pd.DataFrame(columns=std_cols)
        df.rename(columns={v: k for k, v in cols.items() if v in df.columns}, inplace=True)
        if 'harmony_layer' in df.columns:
            df.harmony_layer.fillna(0, inplace=True)
        columns = [c for c in main_cols if c in df.columns]
        additional_cols = {c: c[8:] for c in df.columns if c[:8] == 'Harmony/' and c not in cols.values()}
        df.rename(columns=additional_cols, inplace=True)
        columns += list(additional_cols.values())
        return df[columns]


    def infer_mc(self, mn, mn_onset=0, volta=None):
        """ mn_onset and needs to be converted to mc_onset """
        try:
            mn = int(mn)
        except:
            # Check if MN has volta information, e.g. '16a' for first volta, or '16b' for second etc.
            m = re.match(r"^(\d+)([a-e])$", str(mn))
            if m is None:
                self.logger.error(f"MN {mn} is not a valid measure number.")
                raise
            mn = int(m.group(1))
            volta = ord(m.group(2)) - 96 # turn 'a' into 1, 'b' into 2 etc.
        try:
            mn_onset = frac(mn_onset)
        except:
            self.logger.error(f"The mn_onset {mn_onset} could not be interpreted as a fraction.")
            raise
        measures = self.ml()
        candidates = measures[measures['mn'] == mn]
        if len(candidates) == 0:
            self.logger.error(f"MN {mn} does not occur in measure list, which ends at MN {measures['mn'].max()}.")
            return
        if len(candidates) == 1:
            mc = candidates.iloc[0].mc
            self.logger.debug(f"MN {mn} has unique match with MC {mc}.")
            return mc, mn_onset
        if candidates.volta.notna().any():
            if volta is None:
                mc = candidates.iloc[0].mc
                self.logger.warning(f"""MN {mn} is ambiguous because it is a measure with first and second endings, but volta has not been specified.
The first ending MC {mc} is being used. Suppress this warning by using disambiguating endings such as '16a' for first or '16b' for second.
{candidates[['mc', 'mn', 'mc_offset', 'volta']]}""")
                return mc, mn_onset
            candidates = candidates[candidates.volta == volta]
        if len(candidates) == 1:
            mc = candidates.iloc[0].mc
            self.logger.debug(f"MN {mn}, volta {volta} has unique match with MC {mc}.")
            return mc, mn_onset
        if len(candidates) == 0:
            self.logger.error(f"Volta selection failed")
            return None, None
        if mn_onset == 0:
            mc = candidates.iloc[0].mc
            return mc, mn_onset
        right_boundaries = candidates.act_dur + candidates.act_dur.shift().fillna(0)
        left_boundary = 0
        for i, right_boundary in enumerate(sorted(right_boundaries)):
            j = i
            if mn_onset < right_boundary:
                mc_onset = mn_onset - left_boundary
                break
            left_boundary = right_boundary
        mc = candidates.iloc[j].mc
        if left_boundary == right_boundary:
            self.logger.warning(f"The onset {mn_onset} is bigger than the last possible onset of MN {mn} which is {right_boundary}")
        return mc, mc_onset

    def _get_metadata(self):
        """


        Returns
        -------
        :obj:`dict`
        """
        assert self.soup is not None, "The file's XML needs to be loaded. Get metadata from the 'metadata' property or use the method make_writeable()"
        nav_str2str = lambda s: '' if s is None else str(s)
        data = {tag['name']: nav_str2str(tag.string) for tag in self.soup.find_all('metaTag')}
        if 'reviewer' in data:
            if 'reviewers' in data:
                self.logger.warning("Score properties contain a superfluous key called 'reviewer'. "
                               "Please merge with the value for 'reviewers' and delete.")
            else:
                self.logger.info("The key 'reviewer' contained in the Score properties was automatically "
                            "renamed to 'reviewers' when extracting metadata.")
                data['reviewers'] = data['reviewer']
                del(data['reviewer'])
        if 'annotator' in data:
            if 'annotators' in data:
                self.logger.warning("Score properties contain a superfluous key called 'annotator'. "
                               "Please merge with the value for 'annotators' and delete.")
            else:
                self.logger.info("The key 'annotator' contained in the Score properties was automatically "
                            "renamed to 'annotators' when extracting metadata.")
                data['annotators'] = data['annotator']
                del(data['annotator'])
        for name, value in data.items():
            # check for columns with same name but different capitalization
            name_lwr = name.lower()
            if name == name_lwr:
                continue
            if name_lwr in data:
                self.logger.warning(f"Metadata contain the fields {name} and {name_lwr}. Please merge.")
            elif name_lwr in ('harmony_version', 'annotators', 'reviewers'):
                data[name_lwr] = value
                del(data[name])
                self.logger.warning(f"Wrongly spelled metadata field {name} read as {name_lwr}.")
        data['musescore'] = self.version
        measures = self.ml()
        last_measure = measures.iloc[-1]
        data['last_mc'] = int(last_measure.mc)
        data['last_mn'] = int(last_measure.mn)
        lqb, lqbu = get_quarterbeats_length(measures)
        data['length_qb'] = lqb
        data['length_qb_unfolded'] = lqbu
        data['label_count'] = len(self.get_raw_labels())
        ts_groups, _ = adjacency_groups(measures.timesig)
        mc_ts = measures.groupby(ts_groups)[['mc', 'timesig']].head(1)
        timesigs = dict(mc_ts.values)
        data['TimeSig'] = timesigs
        ks_groups, _ = adjacency_groups(measures.keysig)
        mc_ks = measures.groupby(ks_groups)[['mc', 'keysig']].head(1)
        keysigs = dict(mc_ks.values)
        data['KeySig']  = keysigs
        annotated_key = None
        for harmony_tag in self.soup.find_all('Harmony'):
            label = harmony_tag.find('name')
            if label is not None and label.string is not None:
                m = re.match(r"^\.?([A-Ga-g](#+|b+)?)", label.string)
                if m is not None:
                    annotated_key = m.group(1)
                    break
        if annotated_key is not None:
            data['annotated_key'] = annotated_key
        notes = self.nl()
        if len(notes.index) == 0:
            data['all_notes_qb'] = 0.
            data['n_onsets'] = 0
            return data
        data['all_notes_qb'] = round((notes.duration * 4.).sum(), 2)
        not_tied = ~notes.tied.isin((0, -1))
        data['n_onsets'] = sum(not_tied)
        data['n_onset_positions'] = notes[not_tied].groupby(['mc', 'mc_onset']).size().shape[0]
        staff_groups = notes.groupby('staff').midi
        ambitus = {t.staff: {'min_midi': t.midi, 'min_name': fifths2name(t.tpc, t.midi, logger=self.logger)}
                        for t in notes.loc[staff_groups.idxmin(), ['staff', 'tpc', 'midi', ]].itertuples(index=False)}
        for t in notes.loc[staff_groups.idxmax(), ['staff', 'tpc', 'midi', ]].itertuples(index=False):
            ambitus[t.staff]['max_midi'] = t.midi
            ambitus[t.staff]['max_name'] = fifths2name(t.tpc, t.midi, logger=self.logger)
        data['parts'] = {f"part_{i}": get_part_info(part) for i, part in enumerate(self.soup.find_all('Part'), 1)}
        for part, part_dict in data['parts'].items():
            for id in part_dict['staves']:
                part_dict[f"staff_{id}_ambitus"] = ambitus[id] if id in ambitus else {}
        ambitus_tuples = [tuple(amb_dict.values()) for amb_dict in ambitus.values()]
        mimi, mina, mami, mana = zip(*ambitus_tuples)
        min_midi, max_midi = min(mimi), max(mami)
        data['ambitus'] = {
                            'min_midi': min_midi,
                            'min_name': mina[mimi.index(min_midi)],
                            'max_midi': max_midi,
                            'max_name': mana[mami.index(max_midi)],
                          }
        return data

    @property
    def version(self):
        return str(self.soup.find('programVersion').string)

    def add_standard_cols(self, df):
        """Ensures that the DataFrame's first columns are ['mc', 'mn', 'timesig', 'mc_offset', 'volta']"""
        add_cols = ['mc'] + [c for c in ['mn', 'timesig', 'mc_offset', 'volta'] if c not in df.columns]
        df =  df.merge(self.ml()[add_cols], on='mc', how='left')
        df['mn_onset'] =  df.mc_onset + df.mc_offset
        return df[[col for col in df.columns if not col == 'mc_offset']]


    def delete_label(self, mc, staff, voice, mc_onset, empty_only=False):
        """ Delete a label from a particular position (if there is one).

        Parameters
        ----------
        mc : :obj:`int`
            Measure count.
        staff, voice
            Notational layer in which to delete the label.
        mc_onset : :obj:`fractions.Fraction`
            mc_onset
        empty_only : :obj:`bool`, optional
            Set to True if you want to delete only empty harmonies. Since normally all labels at the defined position
            are deleted, this flag is needed to prevent deleting non-empty <Harmony> tags.

        Returns
        -------
        :obj:`bool`
            Whether a label was deleted or not.
        """
        self.make_writeable()
        measure = self.tags[mc][staff][voice]
        if mc_onset not in measure:
            self.logger.warning(f"Nothing to delete for MC {mc} mc_onset {mc_onset} in staff {staff}, voice {voice}.")
            return False
        elements = measure[mc_onset]
        element_names = [e['name'] for e in elements]
        if not 'Harmony' in element_names:
            self.logger.warning(f"No harmony found at MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice}.")
            return False
        if 'Chord' in element_names and 'location' in element_names:
            NotImplementedError(f"Check MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice}:\n{elements}")
        onsets = sorted(measure)
        ix = onsets.index(mc_onset)
        is_first = ix == 0
        is_last = ix == len(onsets) - 1
        # delete_locations = True

        _, name = get_duration_event(elements)
        if name is None:
            # this label is not attached to a chord or rest and depends on <location> tags, i.e. <location> tags on
            # previous and subsequent onsets might have to be adapted
            n_locs = element_names.count('location')
            if is_first:
                all_dur_ev = sum(True for os, tag_list in measure.items() if get_duration_event(tag_list)[0] is not None)
                if all_dur_ev > 0:
                    assert n_locs > 0, f"""The label on MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice} is the first onset
in a measure with subsequent durational events but has no <location> tag"""
                prv_n_locs = 0
                # if not is_last:
                #     delete_locations = False
            else:
                prv_onset = onsets[ix - 1]
                prv_elements = measure[prv_onset]
                prv_names = [e['name'] for e in prv_elements]
                prv_n_locs = prv_names.count('location')

            if n_locs == 0:
                # The current onset has no <location> tag. This presumes that it is the last onset in the measure.
                if not is_last:
                    raise NotImplementedError(
f"The label on MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice} is not on the last onset but has no <location> tag.")
                if prv_n_locs > 0 and len(element_names) == 1:
                    # this harmony is the only event on the last onset, therefore the previous <location> tag can be deleted
                    if prv_names[-1] != 'location':
                        raise NotImplementedError(
f"Location tag is not the last element in MC {mc}, mc_onset {onsets[ix-1]}, staff {staff}, voice {voice}.")
                    prv_elements[-1]['tag'].decompose()
                    del(measure[prv_onset][-1])
                    if len(measure[prv_onset]) == 0:
                        del(measure[prv_onset])
                    self.logger.debug(f"""Removed <location> tag in MC {mc}, mc_onset {prv_onset}, staff {staff}, voice {voice}  
because it precedes the label to be deleted which is the voice's last onset, {mc_onset}.""")

            elif n_locs == 1:
                if not is_last and not is_first:
                    # This presumes that the previous onset has at least one <location> tag which needs to be adapted
#                     assert prv_n_locs > 0, f"""The label on MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice} locs forward
# but the previous onset {prv_onset} has no <location> tag."""
#                     if prv_names[-1] != 'location':
#                         raise NotImplementedError(
#     f"Location tag is not the last element in MC {mc}, mc_onset {prv_onset}, staff {staff}, voice {voice}.")
                    if prv_n_locs > 0:
                        cur_loc_dur = frac(elements[element_names.index('location')]['duration'])
                        prv_loc_dur = frac(prv_elements[-1]['duration'])
                        prv_loc_tag = prv_elements[-1]['tag']
                        new_loc_dur = prv_loc_dur + cur_loc_dur
                        prv_loc_tag.fractions.string = str(new_loc_dur)
                        measure[prv_onset][-1]['duration'] = new_loc_dur
                    else:
                        self.logger.debug(f"""The label on MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice} locs forward 
# but the previous onset {prv_onset} has no <location> tag:\n{prv_elements}""")
                # else: proceed with deletion

            elif n_locs == 2:
                # this onset has two <location> tags meaning that if the next onset has a <location> tag, too, a second
                # one needs to be added
                assert prv_n_locs == 0, f"""The label on MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice} has two 
<location> tags but the previous onset {prv_onset} has one, too."""
                if not is_last:
                    nxt_onset = onsets[ix + 1]
                    nxt_elements = measure[nxt_onset]
                    nxt_names = [e['name'] for e in nxt_elements]
                    nxt_n_locs = nxt_names.count('location')
                    _, nxt_name = get_duration_event(nxt_elements)
                    if nxt_name is None:
                        # The next onset is neither a chord nor a rest and therefore it needs to have exactly one
                        # location tag and a second one needs to be added based on the first one being deleted
                        nxt_is_last = ix + 1 == len(onsets) - 1
                        if not nxt_is_last:
                            assert nxt_n_locs == 1, f"""The label on MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice} has two 
<location> tags but the next onset {nxt_onset} has {nxt_n_locs if nxt_n_locs > 1 else 
"none although it's neither a chord nor a rest, nor the last onset,"}."""
                            if nxt_names[-1] != 'location':
                                raise NotImplementedError(
f"Location tag is not the last element in MC {mc}, mc_onset {nxt_onset}, staff {staff}, voice {voice}.")
                        if element_names[-1] != 'location':
                            raise NotImplementedError(
f"Location tag is not the last element in MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice}.")
                        neg_loc_dur = frac(elements[element_names.index('location')]['duration'])
                        assert neg_loc_dur < 0, f"""Location tag in MC {mc}, mc_onset {nxt_onset}, staff {staff}, voice {voice}
should be negative but is {neg_loc_dur}."""
                        pos_loc_dur = frac(elements[-1]['duration'])
                        new_loc_value = neg_loc_dur + pos_loc_dur
                        new_tag = self.new_location(new_loc_value)
                        nxt_elements[0]['tag'].insert_before(new_tag)
                        remember = {
                            'name': 'location',
                            'duration': new_loc_value,
                            'tag': new_tag
                        }
                        measure[nxt_onset].insert(0, remember)
                        self.logger.debug(f"""Added a new negative <location> tag to the subsequent mc_onset {nxt_onset} in 
order to prepare the label deletion on MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice}.""")
                # else: proceed with deletions because it has no effect on a subsequent onset
            else:
                raise NotImplementedError(
f"Too many location tags in MC {mc}, mc_onset {prv_onset}, staff {staff}, voice {voice}.")
        # else: proceed with deletions because the <Harmony> is attached to a durational event (Rest or Chord)

        ##### Here the actual removal takes place.
        deletions = []
        delete_location = False
        if name is None and 'location' in element_names:
            other_elements = sum(e not in ('Harmony', 'location') for e in element_names)
            delete_location = is_last or (mc_onset > 0 and other_elements == 0)
        labels = [e for e in elements if e['name'] == 'Harmony']
        if empty_only:
            empty = [e for e in labels if e['tag'].find('name') is None or e['tag'].find('name').string is None]
            if len(empty) == 0:
                self.logger.info(f"No empty label to delete at MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice}.")
            elif len(empty) < len(labels):
                # if there are additional non-empty labels, delete nothing but the empty ones
                elements = empty


        for i, e in enumerate(elements):
            if e['name'] == 'Harmony' or (e['name']  == 'location' and delete_location):
                e['tag'].decompose()
                deletions.append(i)
                self.logger.debug(f"<{e['name']}>-tag deleted in MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice}.")
        for i in reversed(deletions):
            del(measure[mc_onset][i])
        if len(measure[mc_onset]) == 0:
            del(measure[mc_onset])
        self.remove_empty_voices(mc, staff)
        return len(deletions) > 0


    def remove_empty_voices(self, mc, staff):
        voice_tags = self.measure_nodes[staff][mc].find_all('voice')
        dict_keys = sorted(self.tags[mc][staff])
        assert len(dict_keys) == len(voice_tags), f"""In MC {mc}, staff {staff}, there are {len(voice_tags)} <voice> tags
but the keys of _MSCX_bs4.tags[{mc}][{staff}] are {dict_keys}."""
        for key, tag in zip(reversed(dict_keys), reversed(voice_tags)):
            if len(self.tags[mc][staff][key]) == 0:
                tag.decompose()
                del(self.tags[mc][staff][key])
                self.logger.debug(f"Empty <voice> tag of voice {key} deleted in MC {mc}, staff {staff}.")
            else:
                # self.logger.debug(f"No superfluous <voice> tags in MC {mc}, staff {staff}.")
                break

    def make_writeable(self):
        if self.read_only:
            self.read_only = False
            with temporarily_suppress_warnings(self) as self:
                # This is an automatic re-parse which does not have to be logged again
                self.parse_measures()


    def add_label(self, label, mc, mc_onset, staff=1, voice=1, **kwargs):
        """ Adds a single label to the current XML in form of a new
        <Harmony> (and maybe also <location>) tag.

        Parameters
        ----------
        label
        mc
        mc_onset
        staff
        voice
        kwargs

        Returns
        -------

        """
        if pd.isnull(label) and len(kwargs) == 0:
            self.logger.error(f"Label cannot be '{label}'")
            return False
        assert mc_onset >= 0, f"Cannot attach label {label} to negative onset {mc_onset} at MC {mc}, staff {staff}, voice {voice}"
        self.make_writeable()
        if mc not in self.tags:
            self.logger.error(f"MC {mc} not found.")
            return False
        if staff not in self.measure_nodes:
            try:
                # maybe a negative integer?
                staff = list(self.measure_nodes.keys())[staff]
            except:
                self.logger.error(f"Staff {staff} not found.")
                return False
        if voice not in [1, 2, 3, 4]:
            self.logger.error(f"Voice needs to be 1, 2, 3, or 4, not {voice}.")
            return False

        mc_onset = frac(mc_onset)
        label_name = kwargs['decoded'] if 'decoded' in kwargs else label
        if voice not in self.tags[mc][staff]:
            # Adding label to an unused voice that has to be created
            existing_voices = self.measure_nodes[staff][mc].find_all('voice')
            n = len(existing_voices)
            if not voice <= n:
                last = existing_voices[-1]
                while voice > n:
                    last = self.new_tag('voice', after=last)
                    n += 1
                remember = self.insert_label(label=label, loc_before=None if mc_onset == 0 else mc_onset, within=last, **kwargs)
                self.tags[mc][staff][voice] = defaultdict(list)
                self.tags[mc][staff][voice][mc_onset] = remember
                self.logger.debug(f"Added {label_name} to empty {voice}{ordinal_suffix(voice)} voice in MC {mc} at mc_onset {mc_onset}.")
                return True

        measure = self.tags[mc][staff][voice]
        if mc_onset in measure:
            # There is an event (chord or rest) with the same onset to attach the label to
            elements = measure[mc_onset]
            names = [e['name'] for e in elements]
            _, name = get_duration_event(elements)
            # insert before the first tag that is not in the tags_before_label list
            tags_before_label = ['BarLine', 'Clef', 'Dynamic', 'endTuplet', 'FiguredBass', 'KeySig', 'location', 'StaffText', 'Tempo', 'TimeSig']
            try:
                ix, before = next((i, element['tag']) for i, element in enumerate(elements) if element['name'] not in
                              tags_before_label )
                remember = self.insert_label(label=label, before=before, **kwargs)
            except:
                self.logger.debug(f"""'{label}' is to be inserted at MC {mc}, onset {mc_onset}, staff {staff}, voice {voice},
where there is no Chord or Rest, just: {elements}.""")
                l = len(elements)
                if 'FiguredBass' in names:
                    ix, after = next((i, elements[i]['tag']) for i in range(l) if elements[i]['name'] == 'FiguredBass')
                else:
                    if l > 1 and names[-1] == 'location':
                        ix = l - 1
                    else:
                        ix = l
                    after = elements[ix-1]['tag']
                remember = self.insert_label(label=label, after=after, **kwargs)
            measure[mc_onset].insert(ix, remember[0])
            old_names = list(names)
            names.insert(ix, 'Harmony')
            if name is None:
                self.logger.debug(f"""MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice} had only these tags (and no <Chord> or <Rest>):
{old_names}\nAfter insertion: {names}""")
            else:
                self.logger.debug(f"Added {label_name} to {name} in MC {mc}, mc_onset {mc_onset}, staff {staff}, voice {voice}.")
            if 'Harmony' in old_names:
                self.logger.debug(
                    f"There had already been a label.")
            return True


        # There is no event to attach the label to
        ordered = list(reversed(sorted(measure)))
        assert len(ordered) > 0, f"MC {mc} empty in staff {staff}, voice {voice}?"
        try:
            prv_pos, nxt_pos = next((prv, nxt)
                                    for prv, nxt
                                    in zip(ordered + [None], [None] + ordered)
                                    if prv < mc_onset)
        except:
            self.logger.error(f"No event occurs before onset {mc_onset} at MC {mc}, staff {staff}, voice {voice}. All elements: {ordered}")
            raise
        prv = measure[prv_pos]
        nxt = None if nxt_pos is None else measure[nxt_pos]
        prv_names = [e['name'] for e in prv]
        prv_ix, prv_name = get_duration_event(prv)
        if nxt is not None:
            nxt_names = [e['name'] for e in nxt]
            _, nxt_name = get_duration_event(nxt)
        prv_name = ', '.join(f"<{e}>" for e in prv_names if e != 'location')
        # distinguish six cases: prv can be [event, location], nxt can be [event, location, None]
        if prv_ix is not None:
            # prv is event (chord or rest)
            if nxt is None:
                loc_after = prv_pos + prv[prv_ix]['duration'] - mc_onset
                # i.e. the ending of the last event minus the onset
                remember = self.insert_label(label=label, loc_before= -loc_after, after=prv[prv_ix]['tag'], **kwargs)
                self.logger.debug(f"Added {label_name} at {loc_after} before the ending of MC {mc}'s last {prv_name}.")
            elif nxt_name is not None or nxt_names.count('location') == 0:
                # nxt is event (chord or rest) or something at onset 1 (after all sounding events, e.g. <Segment>)
                loc_after = nxt_pos - mc_onset
                remember = self.insert_label(label=label, loc_before=-loc_after, loc_after=loc_after,
                                             after=prv[prv_ix]['tag'], **kwargs)
                self.logger.debug(f"MC {mc}: Added {label_name} at {loc_after} before the {nxt_name} at mc_onset {nxt_pos}.")
            else:
                # nxt is not a sounding event and has location tag(s)
                nxt_name = ', '.join(f"<{e}>" for e in nxt_names if e != 'location')
                loc_ix = nxt_names.index('location')
                loc_dur = nxt[loc_ix]['duration']
                assert loc_dur <= 0, f"Positive location tag at MC {mc}, mc_onset {nxt_pos} when trying to insert {label_name} at mc_onset {mc_onset}: {nxt}"
#                 if nxt_pos + loc_dur == mc_onset:
#                     self.logger.info(f"nxt_pos: {nxt_pos}, loc_dur: {loc_dur}, mc_onset: {mc_onset}")
#                     # label to be positioned with the same location
#                     remember = self.insert_label(label=label, after=nxt[-1]['tag'], **kwargs)
#                     self.logger.debug(
#                         f"""MC {mc}: Joined {label_name} with the {nxt_name} occuring at {loc_dur} before the ending
# of the {prv_name} at mc_onset {prv_pos}.""")
#                 else:
                loc_before = loc_dur - nxt_pos + mc_onset
                remember = self.insert_label(label=label, loc_before=loc_before, before=nxt[loc_ix]['tag'], **kwargs)
                loc_after = nxt_pos - mc_onset
                nxt[loc_ix]['tag'].fractions.string = str(loc_after)
                nxt[loc_ix]['duration'] = loc_after
                self.logger.debug(f"""MC {mc}: Added {label_name} at {-loc_before} before the ending of the {prv_name} at mc_onset {prv_pos}
and {loc_after} before the subsequent\n{nxt}.""")

        else:
            # prv has location tag(s)
            loc_before = mc_onset - prv_pos
            if nxt is None:
                remember = self.insert_label(label=label, loc_before=loc_before, after=prv[-1]['tag'], **kwargs)
                self.logger.debug(f"MC {mc}: Added {label_name} at {loc_before} after the previous {prv_name} at mc_onset {prv_pos}.")
            else:
                try:
                    loc_ix = next(i for i, name in zip(range(len(prv_names) - 1, -1, -1), reversed(prv_names)) if name == 'location')
                except:
                    self.logger.error(f"Trying to add {label_name} to MC {mc}, staff {staff}, voice {voice}, onset {mc_onset}: The tags of mc_onset {prv_pos} should include a <location> tag but don't:\n{prv}")
                    raise
                prv[loc_ix]['tag'].fractions.string = str(loc_before)
                prv[loc_ix]['duration'] = loc_before
                loc_after = nxt_pos - mc_onset
                remember = self.insert_label(label=label, loc_after=loc_after, after=prv[loc_ix]['tag'], **kwargs)
                if nxt_name is None:
                    nxt_name = ', '.join(f"<{e}>" for e in nxt_names if e != 'location')
                self.logger.debug(f"""MC {mc}: Added {label_name} at {loc_before} after the previous {prv_name} at mc_onset {prv_pos}
and {loc_after} before the subsequent {nxt_name}.""")

        # if remember[0]['name'] == 'location':
        #     measure[prv_pos].append(remember[0])
        #     measure[mc_onset] = remember[1:]
        # else:
        measure[mc_onset] = remember
        return True






    def insert_label(self, label, loc_before=None, before=None, loc_after=None, after=None, within=None, **kwargs):
        tag = self.new_label(label, before=before, after=after, within=within, **kwargs)
        remember = [dict(
                        name = 'Harmony',
                        duration = frac(0),
                        tag = tag
                    )]
        if loc_before is not None:
            location = self.new_location(loc_before)
            tag.insert_before(location)
            remember.insert(0, dict(
                        name = 'location',
                        duration =loc_before,
                        tag = location
                    ))
        if loc_after is not None:
            location = self.new_location(loc_after)
            tag.insert_after(location)
            remember.append(dict(
                        name = 'location',
                        duration =loc_after,
                        tag =location
                    ))
        return remember


    def change_label_color(self, mc, mc_onset, staff, voice, label, color_name=None, color_html=None, color_r=None, color_g=None, color_b=None, color_a=None):
        """  Change the color of an existing label.

        Parameters
        ----------
        mc : :obj:`int`
            Measure count of the label
        mc_onset : :obj:`fractions.Fraction`
            Onset position to which the label is attached.
        staff : :obj:`int`
            Staff to which the label is attached.
        voice : :obj:`int`
            Notational layer to which the label is attached.
        label : :obj:`str`
            (Decoded) label.
        color_name, color_html : :obj:`str`, optional
            Two ways of specifying the color.
        color_r, color_g, color_b, color_a : :obj:`int` or :obj:`str`, optional
            To specify a RGB color instead, pass at least, the first three. ``color_a`` (alpha = opacity) defaults
            to 255.
        """
        if label == 'empty_harmony':
            self.logger.debug("Empty harmony was skipped because the color wouldn't change anything.")
            return True
        params = [color_name, color_html, color_r, color_g, color_b, color_a]
        rgba = color_params2rgba(*params)
        if rgba is None:
            given_params = [p for p in params if p is not None]
            self.logger.warning(f"Parameters could not be turned into a RGBA color: {given_params}")
            return False
        self.make_writeable()
        if mc not in self.tags:
            self.logger.error(f"MC {mc} not found.")
            return False
        if staff not in self.tags[mc]:
            self.logger.error(f"Staff {staff} not found.")
            return False
        if voice not in [1, 2, 3, 4]:
            self.logger.error(f"Voice needs to be 1, 2, 3, or 4, not {voice}.")
            return False
        if voice not in self.tags[mc][staff]:
            self.logger.error(f"Staff {staff}, MC {mc} has no voice {voice}.")
            return False
        measure = self.tags[mc][staff][voice]
        mc_onset = frac(mc_onset)
        if mc_onset not in measure:
            self.logger.error(f"Staff {staff}, MC {mc}, voice {voice} has no event on mc_onset {mc_onset}.")
            return False
        elements = measure[mc_onset]
        harmony_tags = [e['tag'] for e in elements if e['name'] == 'Harmony']
        n_labels = len(harmony_tags)
        if n_labels == 0:
            self.logger.error(f"Staff {staff}, MC {mc}, voice {voice}, mc_onset {mc_onset} has no labels.")
            return False
        labels = [decode_harmony_tag(t) for t in harmony_tags]
        try:
            ix = labels.index(label)
        except:
            self.logger.error(f"Staff {staff}, MC {mc}, voice {voice}, mc_onset {mc_onset} has no label '{label}'.")
            return False
        tag = harmony_tags[ix]
        attrs = rgba2attrs(rgba)
        if tag.color is None:
            tag_order = ['absolute_base', 'function', 'name', 'rootCase', 'absolute_root']
            after = next(tag.find(t) for t in tag_order if tag.find(t) is not None)
            self.new_tag('color', attributes=attrs, after=after)
        else:
            for k, v in attrs.items():
                tag.color[k] = v
        return True







    def new_label(self, label, harmony_layer=None, after=None, before=None, within=None, absolute_root=None, rootCase=None, absolute_base=None,
                  leftParen=None, rightParen=None, offset_x=None, offset_y=None, nashville=None, decoded=None,
                  color_name=None, color_html=None, color_r=None, color_g=None, color_b=None, color_a=None,
                  placement=None, minDistance=None, style=None, z=None):
        tag = self.new_tag('Harmony')
        if not pd.isnull(harmony_layer):
            try:
                harmony_layer = int(harmony_layer)
            except:
                if harmony_layer[0] in ('1', '2'):
                    harmony_layer = int(harmony_layer[0])
            # only include <harmonyType> tag for harmony_layer 1 and 2 (MuseScore's Nashville Numbers and Roman Numerals)
            if harmony_layer in (1, 2):
                _ = self.new_tag('harmonyType', value=harmony_layer, within=tag)
        if not pd.isnull(leftParen):
            _ = self.new_tag('leftParen', within=tag)
        if not pd.isnull(absolute_root):
            _ = self.new_tag('root', value=absolute_root, within=tag)
        if not pd.isnull(rootCase):
            _ = self.new_tag('rootCase', value=rootCase, within=tag)
        if not pd.isnull(label):
            if label == '/':
                label = ""
            _ = self.new_tag('name', value=label, within=tag)
        else:
            assert not pd.isnull(absolute_root), "Either label or root need to be specified."

        if not pd.isnull(z):
            _ = self.new_tag('z', value=z, within=tag)
        if not pd.isnull(style):
            _ = self.new_tag('style', value=style, within=tag)
        if not pd.isnull(placement):
            _ = self.new_tag('placement', value=placement, within=tag)
        if not pd.isnull(minDistance):
            _ = self.new_tag('minDistance', value=minDistance, within=tag)
        if not pd.isnull(nashville):
            _ = self.new_tag('function', value=nashville, within=tag)
        if not pd.isnull(absolute_base):
            _ = self.new_tag('base', value=absolute_base, within=tag)

        rgba = color_params2rgba(color_name, color_html, color_r, color_g, color_b, color_a)
        if rgba is not None:
            attrs = rgba2attrs(rgba)
            _ = self.new_tag('color', attributes=attrs, within=tag)

        if not pd.isnull(offset_x) or not pd.isnull(offset_y):
            if pd.isnull(offset_x):
                offset_x = '0'
            if pd.isnull(offset_y):
                offset_y = '0'
            _ = self.new_tag('offset', attributes={'x': offset_x, 'y': offset_y}, within=tag)
        if not pd.isnull(rightParen):
            _ = self.new_tag('rightParen', within=tag)
        if after is not None:
            after.insert_after(tag)
        elif before is not None:
            before.insert_before(tag)
        elif within is not None:
            within.append(tag)
        return tag


    def new_location(self, location):
        tag = self.new_tag('location')
        _ = self.new_tag('fractions', value=str(location), within=tag)
        return tag



    def new_tag(self, name, value=None, attributes={}, after=None, before=None, within=None):
        tag = self.soup.new_tag(name)
        if value is not None:
            tag.string = str(value)
        for k, v in attributes.items():
            tag.attrs[k] = v

        if after is not None:
            after.insert_after(tag)
        elif before is not None:
            before.insert_before(tag)
        elif within is not None:
            within.append(tag)

        return tag


    def color_notes(self, from_mc, from_mc_onset, to_mc=None, to_mc_onset=None,
                    midi=[], tpc=[], inverse=False,
                    color_name=None, color_html=None, color_r=None, color_g=None, color_b=None, color_a=None,
                    ):
        """ Colors all notes occurring in a particular score segment in one particular color, or
        only those (not) pertaining to a collection of MIDI pitches or Tonal Pitch Classes (TPC).

        Parameters
        ----------
        from_mc : :obj:`int`
            MC in which the score segment starts.
        from_mc_onset : :obj:`fractions.Fraction`
            mc_onset where the score segment starts.
        to_mc : :obj:`int`, optional
            MC in which the score segment ends. If not specified, the segment ends at the end of the score.
        to_mc_onset : :obj:`fractions.Fraction`, optional
            If ``to_mc`` is defined, the mc_onset where the score segment ends.
        midi : :obj:`Collection[int]`, optional
            Collection of MIDI numbers to use as a filter or an inverse filter (depending on ``inverse``).
        tpc : :obj:`Collection[int]`, optional
            Collection of Tonal Pitch Classes (C=0, G=1, F=-1 etc.) to use as a filter or an inverse filter (depending on ``inverse``).
        inverse : :obj:`bool`, optional
            By default, only notes where all specified filters (midi and/or tpc) apply are colored.
            Set to True to color only those notes where none of the specified filters match.
        color_name : :obj:`str`, optional
            Specify the color either as a name, or as HTML color, or as RGB(A). As a name you can
            use CSS colors or MuseScore colors (see :py:attr:`utils.MS3_COLORS`).
        color_html : :obj:`str`, optional
            Specify the color either as a name, or as HTML color, or as RGB(A). An HTML color
            needs to be string of length 6.
        color_r : :obj:`int`, optional
            If you specify the color as RGB(A), you also need to specify color_g and color_b.
        color_g : :obj:`int`, optional
            If you specify the color as RGB(A), you also need to specify color_r and color_b.
        color_b : :obj:`int`, optional
            If you specify the color as RGB(A), you also need to specify color_r and color_g.
        color_a : :obj:`int`, optional
            If you have specified an RGB color, the alpha value defaults to 255 unless specified otherwise.

        Returns
        -------
        :obj:`list`
            List of durations (in fractions) of all notes that have been colored.
        :obj:`list`
            List of durations (in fractions) of all notes that have not been colored.
        """
        if len(self.tags) == 0:
            if self.read_only:
                self.logger.error("Score is read_only.")
            else:
                self.logger.error(f"Score does not include any parsed tags.")
            return

        rgba = color_params2rgba(color_name, color_html, color_r, color_g, color_b, color_a)
        if rgba is None:
            self.logger.error(f"Pass a valid color value.")
            return
        if color_name is None:
            color_name = rgb_tuple2format(rgba[:3], format='name')
        color_attrs = rgba2attrs(rgba)

        str_midi = [str(m) for m in midi]
        # MuseScore's TPCs are shifted such that C = 14:
        ms_tpc = [str(t + 14) for t in tpc]

        until_end = pd.isnull(to_mc)
        negation = ' not' if inverse else ''
        colored_durations, untouched_durations = [], []
        for mc, staves in self.tags.items():
            if mc < from_mc or (not until_end and mc > to_mc):
                continue
            for staff, voices in staves.items():
                for voice, onsets in voices.items():
                    for onset, tag_dicts in onsets.items():
                        if mc == from_mc and onset < from_mc_onset:
                            continue
                        if not until_end and mc == to_mc and onset >= to_mc_onset:
                            continue
                        for tag_dict in tag_dicts:
                            if tag_dict['name'] != 'Chord':
                                continue
                            duration = tag_dict['duration']
                            for note_tag in tag_dict['tag'].find_all('Note'):
                                reason = ""
                                if len(midi) > 0:
                                    midi_val = note_tag.pitch.string
                                    if inverse and midi_val in str_midi:
                                        untouched_durations.append(duration)
                                        continue
                                    if not inverse and midi_val not in str_midi:
                                        untouched_durations.append(duration)
                                        continue
                                    reason = f"MIDI pitch {midi_val} is{negation} in {midi}"
                                if len(ms_tpc) > 0:
                                    tpc_val = note_tag.tpc.string
                                    if inverse and tpc_val in ms_tpc:
                                        untouched_durations.append(duration)
                                        continue
                                    if not inverse and tpc_val not in ms_tpc:
                                        untouched_durations.append(duration)
                                        continue
                                    if reason != "":
                                        reason += " and "
                                    reason += f"TPC {int(tpc_val) - 14} is{negation} in {tpc}"
                                if reason == "":
                                    reason = " because no filters were specified."
                                else:
                                    reason = " because " + reason
                                first_inside = note_tag.find()
                                _ = self.new_tag('color', attributes=color_attrs, before=first_inside)
                                colored_durations.append(duration)
                                self.logger.debug(f"MC {mc}, onset {onset}, staff {staff}, voice {voice}: Changed note color to {color_name}{reason}.")
        return colored_durations, untouched_durations

    # def close_file_handlers(self):
    #     for h in self.logger.logger.handlers:
    #         if h.__class__ == logging.FileHandler:
    #             h.close()


    def __getstate__(self):
        """When pickling, make object read-only, i.e. delete the BeautifulSoup object and all references to tags."""
        super().__getstate__()
        self.soup = None
        self.tags = {}
        self.measure_nodes = {k: None for k in self.measure_nodes.keys()}
        self.read_only = True
        return self.__dict__


#######################################################################
####################### END OF CLASS DEFINITION #######################
#######################################################################

class Metatags:
    """Easy way to read and write any style information in a parsed MSCX score."""

    def __init__(self, soup):
        self.soup = soup

    @property
    def tags(self):
        return {tag['name']: tag for tag in self.soup.find_all('metaTag')}

    def __getitem__(self, attr):
        tags = self.tags
        if attr in tags:
            val = tags[attr].string
            return '' if val is None else str(val)
        return None

    def __setitem__(self, attr, val):
        tags = self.tags
        if attr in tags:
            tags[attr].string = str(val)
        else:
            new_tag = self.soup.new_tag('metaTag')
            new_tag.attrs['name'] = attr
            new_tag.string = str(val)
            for insert_here in tags.keys():
                if insert_here > attr:
                    break
            tags[insert_here].insert_before(new_tag)

    def __repr__(self):
        return '\n'.join(str(t) for t in self.tags.values())


class Style:
    """Easy way to read and write any style information in a parsed MSCX score."""

    def __init__(self, soup):
        self.soup = soup
        self.style = self.soup.find('Style')
        assert self.style is not None, "No <Style> tag found."

    def __getitem__(self, attr):
        tag = self.style.find(attr)
        if tag is None:
            return None
        val = tag.string
        return '' if val is None else str(val)

    def __setitem__(self, attr, val):
        if attr in self:
            tag = self.style.find(attr)
            tag.string = str(val)
        else:
            new_tag = self.soup.new_tag(attr)
            new_tag.string = str(val)
            self.style.append(new_tag)

    def __iter__(self):
        tags = self.style.find_all()
        return (t.name for t in tags)

    def __repr__(self):
        tags = self.style.find_all()
        return ', '.join(t.name for t in tags)


def get_duration_event(elements):
    """ Receives a list of dicts representing the events for a given mc_onset and returns the index and name of
    the first event that has a duration, so either a Chord or a Rest."""
    names = [e['name'] for e in elements]
    if 'Chord' in names or 'Rest' in names:
        if 'Rest' in names:
            ix = names.index('Rest')
            name = '<Rest>'
        else:
            ix = next(i for i, d in enumerate(elements) if d['name'] == 'Chord' and d['duration'] > 0)
            name = '<Chord>'
        return ix, name
    return (None, None)



def get_part_info(part_tag):
    """Instrument names come in different forms in different places. This function extracts the information from a
        <Part> tag and returns it as a dictionary."""
    res = {}
    res['staves'] = [int(staff['id']) for staff in part_tag.find_all('Staff')]
    if part_tag.trackName is not None and part_tag.trackName.string is not None:
        res['trackName'] = part_tag.trackName.string.strip()
    else:
        res['trackName'] = ''
    if part_tag.Instrument is not None:
        instr = part_tag.Instrument
        if instr.longName is not None and instr.longName.string is not None:
            res['longName'] = instr.longName.string.strip()
        if instr.shortName is not None and instr.shortName.string is not None:
            res['shortName'] = instr.shortName.string.strip()
        if instr.trackName is not None and instr.trackName.string is not None:
            res['instrument'] = instr.trackName.string.strip()
        else:
            res['instrument'] = res['trackName']
    return res


@function_logger
def make_spanner_cols(df, spanner_types=None):
    """ From a raw chord list as returned by ``get_chords(spanners=True)``
        create a DataFrame with Spanner IDs for all chords for all spanner
        types they are associated with.

    Parameters
    ----------
    spanner_types : :obj:`collection`
        If this parameter is passed, only the enlisted
        spanner types ['Slur', 'HairPin', 'Pedal', 'Ottava'] are included.

    """
    #### History of this algorithm:
    #### At first, spanner IDs were written to Chords of the same layer until a prev/location was found. At first this
    #### caused some spanners to continue until the end of the piece because endings were missing when selecting based
    #### on the subtype column (endings don't specify subtype). After fixing this, there were still mistakes, particularly for slurs, because:
    #### 1. endings can be missing, 2. endings can occur in a different voice than they should, 3. endings can be
    #### expressed with different values then the beginning (all three cases found in ms3/old_tests/MS3/stabat_03_coloured.mscx)
    #### Therefore, the new algorithm ends spanners simply after their given duration.

    cols = {
        'nxt_m': 'Spanner/next/location/measures',
        'nxt_f': 'Spanner/next/location/fractions',
        #'prv_m': 'Spanner/prev/location/measures',
        #'prv_f': 'Spanner/prev/location/fractions',
        'type':  'Spanner:type',
        }
    # nxt = beginning of spanner & indication of its duration
    # (prv = ending of spanner & negative duration supposed to match nxt)

    def get_spanner_ids(spanner_type, subtype=None):
        if spanner_type == 'Slur':
            f_cols = ['Chord/' + cols[c] for c in ['nxt_m', 'nxt_f']]  ##, 'prv_m', 'prv_f']]
            type_col = 'Chord/' + cols['type']
        else:
            f_cols = [cols[c] for c in ['nxt_m', 'nxt_f']]  ##, 'prv_m', 'prv_f']]
            type_col = cols['type']

        subtype_col = f"Spanner/{spanner_type}/subtype"
        if subtype is None and subtype_col in df:
            # automatically generate one column per available subtype
            subtypes = set(df.loc[df[subtype_col].notna(), subtype_col])
            results = [get_spanner_ids(spanner_type, st) for st in subtypes]
            return dict(ChainMap(*results))

        # select rows corresponding to spanner_type
        sel = df[type_col] == spanner_type
        # then select only beginnings
        existing = [c for c in f_cols if c in df.columns]
        sel &= df[existing].notna().any(axis=1)
        if subtype is not None:
            sel &= df[subtype_col] == subtype
        features = pd.DataFrame(index=df.index, columns=f_cols)
        features.loc[sel, existing] = df.loc[sel, existing]
        features.iloc[:, 0] = features.iloc[:, 0].fillna(0).astype(int).abs()  # nxt_m
        features.iloc[:, 1] = features.iloc[:, 1].fillna(0).map(frac)          # nxt_f
        features = pd.concat([df[['mc', 'mc_onset', 'staff']], features], axis=1)

        current_id = -1
        column_name = spanner_type
        if subtype:
            column_name += ':' + subtype
        distinguish_voices = spanner_type in ['Slur', 'Trill']
        if distinguish_voices:
            # slurs need to be ended by the same voice, there can be several going on in parallel in different voices
            features.insert(3, 'voice', df.voice)
            staff_stacks = {(i, v): {} for i in df.staff.unique() for v in range(1, 5)}
        else:
            # For all other spanners, endings can be encoded in any of the 4 voices
            staff_stacks = {i: {} for i in df.staff.unique()}
        # staff_stacks contains for every possible layer a dictionary  {ID -> (end_mc, end_f)};
        # going through chords chronologically, output all "open" IDs for the current layer until they are closed, i.e.
        # removed from the stack

        def spanner_ids(row, distinguish_voices=False):
            nonlocal staff_stacks, current_id
            if distinguish_voices:
                mc, mc_onset, staff, voice, nxt_m, nxt_f = row
                layer = (staff, voice)
            else:
                mc, mc_onset, staff, nxt_m, nxt_f = row
                layer = staff

            beginning = nxt_m > 0 or nxt_f != 0
            if beginning:
                current_id += 1
                staff_stacks[layer][current_id] = (mc + nxt_m, mc_onset + nxt_f)
            for id, (end_mc, end_f) in tuple(staff_stacks[layer].items()):
                if end_mc < mc or (end_mc == mc and end_f < mc_onset):
                    del(staff_stacks[layer][id])
            val = ', '.join(str(i) for i in staff_stacks[layer].keys())
            return val if val != '' else pd.NA


        # create the ID column for the currently selected spanner (sub)type
        res = {column_name: [spanner_ids(row, distinguish_voices=distinguish_voices) for row in features.values]}
        ### With the new algorithm, remaining 'open' spanners result from no further event occurring in the respective layer
        ### after the end of the last spanner.
        # open_ids = {layer: d for layer, d in staff_stacks.items() if len(d) > 0}
        # if len(open_ids) > 0:
        #     logger.warning(f"At least one of the spanners of type {spanner_type}{'' if subtype is None else ', subtype: ' + subtype} "
        #                    f"has not been closed: {open_ids}")
        return res

    type_col = cols['type']
    types = list(set(df.loc[df[type_col].notna(), type_col])) if type_col in df.columns else []
    if 'Chord/' + type_col in df.columns:
        types += ['Slur']
    if spanner_types is not None:
        types = [t for t in types if t in spanner_types]
    list_of_dicts = [get_spanner_ids(t) for t in types]
    merged_dict = dict(ChainMap(*list_of_dicts))
    renaming = {
        'HairPin:0': 'crescendo_hairpin',
        'HairPin:1': 'decrescendo_hairpin',
        'HairPin:2': 'crescendo_line',
        'HairPin:3': 'diminuendo_line',
        'Slur': 'slur',
        'Pedal': 'pedal'
    }
    return pd.DataFrame(merged_dict, index=df.index).rename(columns=renaming)




def make_tied_col(df, tie_col, next_col, prev_col):
    new_col = pd.Series(pd.NA, index=df.index, name='tied')
    if tie_col not in df.columns:
        return new_col
    has_tie = df[tie_col].fillna('').str.contains('Tie')
    if has_tie.sum() == 0:
        return new_col
    # merge all columns whose names start with `next_col` and `prev_col` respectively
    next_cols = [col for col in df.columns if col[:len(next_col)] == next_col]
    nxt = df[next_cols].notna().any(axis=1)
    prev_cols = [col for col in df.columns if col[:len(prev_col)] == prev_col]
    prv = df[prev_cols].notna().any(axis=1)
    new_col = new_col.where(~has_tie, 0).astype('Int64')
    tie_starts = has_tie & nxt
    tie_ends = has_tie & prv
    new_col.loc[tie_ends] -= 1
    new_col.loc[tie_starts] += 1
    return new_col


def safe_update(old, new):
    """ Update dict without replacing values.
    """
    existing = [k for k in new.keys() if k in old]
    if len(existing) > 0:
        new = dict(new)
        for ex in existing:
            old[ex] = f"{old[ex]} & {new[ex]}"
            del (new[ex])
    old.update(new)


def recurse_node(node, prepend=None, exclude_children=None):
    """ The heart of the XML -> DataFrame conversion. Changes may have ample repercussions!

    Returns
    -------
    :obj:`dict`
        Keys are combinations of tag (& attribute) names, values are value strings.
    """
    def tag_or_string(c, ignore_empty=False):
        nonlocal info, name
        if isinstance(c, bs4.element.Tag):
            if c.name not in exclude_children:
                safe_update(info, {child_prepend + k: v for k, v in recurse_node(c, prepend=c.name).items()})
        elif c not in ['\n', None]:
            info[name] = str(c)
        elif not ignore_empty:
            if c == '\n':
                info[name] = '∅'
            elif c is None:
                info[name] = '/'


    info = {}
    if exclude_children is None:
        exclude_children = []
    name = node.name if prepend is None else prepend
    attr_prepend = name + ':'
    child_prepend = '' if prepend is None else prepend + '/'
    for attr, value in node.attrs.items():
        info[attr_prepend + attr] = value
    children = tuple(node.children)
    if len(children) > 1:
        for c in children:
            tag_or_string(c, ignore_empty=True)
    elif len(children) == 1:
        tag_or_string(children[0], ignore_empty=False)
    else:
        info[name] = '/'
    return info



def bs4_chord_duration(node, duration_multiplier=1):

    durationtype = node.find('durationType').string
    if durationtype == 'measure' and node.find('duration'):
        nominal_duration = frac(node.find('duration').string)
    else:
        nominal_duration = _MSCX_bs4.durations[durationtype]
    dots = node.find('dots')
    dotmultiplier = sum([frac(1 / 2) ** i for i in range(int(dots.string) + 1)]) if dots else 1
    return nominal_duration * duration_multiplier * dotmultiplier, dotmultiplier


def bs4_rest_duration(node, duration_multiplier=1):
    return bs4_chord_duration(node, duration_multiplier)


def decode_harmony_tag(tag):
    """ Decode a <Harmony> tag into a string."""
    label = ''
    if tag.function is not None:
        label = str(tag.function.string)
    if tag.leftParen is not None:
        label = '('
    if tag.root is not None:
        root = fifths2name(tag.root.string, ms=True)
        if str(tag.rootCase) == '1':
            root = root.lower()
        label += root
    name = tag.find('name')
    if name is not None:
        label += str(name.string)
    if tag.base is not None:
        label += '/' + str(tag.base.string)
    if tag.rightParen is not None:
        label += ')'
    return label


############ Functions for writing BeautifulSoup to MSCX file

def escape_string(s):
    return str(s).replace('&', '&amp;')\
                 .replace('"', '&quot;')\
                 .replace('<', '&lt;')\
                 .replace('>', '&gt;')

def opening_tag(node, closed=False):
    result = f"<{node.name}"
    attributes = node.attrs
    if len(attributes) > 0:
        result += ' ' + ' '.join(f'{attr}="{escape_string(value)}"' for attr, value in attributes.items())
    closing = '/' if closed else ''
    return f"{result}{closing}>"


def closing_tag(node_name):
    return f"</{node_name}>"


def make_oneliner(node):
    """ Pass a tag of which the layout does not spread over several lines. """
    result = opening_tag(node)
    for c in node.children:
        if isinstance(c, bs4.element.Tag):
            result += make_oneliner(c)
        else:
            result += escape_string(c)
    result += closing_tag(node.name)
    return result


def format_node(node, indent):
    """ Recursively format Beautifulsoup tag as in an MSCX file."""
    nxt_indent = indent + 2
    space = indent * ' '
    node_name = node.name
    # The following tags are exceptionally not abbreviated when empty,
    # so for instance you get <metaTag></metaTag> and not <metaTag/>
    if node_name in ['continueAt', 'continueText', 'endText', 'LayerTag', 'metaTag', 'name', 'programRevision', 'text', 'trackName']:
        return f"{space}{make_oneliner(node)}\n"
    children = node.find_all(recursive=False)
    if len(children) > 0:
        result = f"{space}{opening_tag(node)}\n"
        result += ''.join(format_node(child, nxt_indent) for child in children)
        result += f"{nxt_indent * ' '}{closing_tag(node_name)}\n"
        return result
    if node.string == '\n':
        return f"{space}{opening_tag(node)}\n{nxt_indent * ' '}{closing_tag(node_name)}\n"
    if node.string is None:
        return f"{space}{opening_tag(node, closed=True)}\n"
    return f"{space}{make_oneliner(node)}\n"


def bs4_to_mscx(soup):
    """ Turn the BeautifulSoup into a string representing an MSCX file"""
    assert soup is not None, "BeautifulSoup XML structure is None"
    initial_tag = """<?xml version="1.0" encoding="UTF-8"?>\n"""
    first_tag = soup.find()
    return initial_tag + format_node(first_tag, indent=0)

