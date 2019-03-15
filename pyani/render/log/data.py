

class AniRenderData():

    def __init__(self):
        '''
        Data stored as
        {
            sequence: {
                shot: {
                    history: {
                        frame: {
                            stat: {
                                item(s)
                            },
                            more stats...
                        },
                        more frames...
                    },
                    more history...
                },
                more shots...
            },
            more sequences...
        }
        '''
        self.__data = {
            "seq040": {
                "shot010": {
                    "1": {
                        "1001": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        },
                        "1050": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        }
                    },
                    "2": {
                        "1002": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        },
                        "1003": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        }
                    }
                },
                "shot070": {
                    "1": {
                        "1010": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        },
                        "1050": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        }
                    },
                    "2": {
                        "1001": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        },
                        "1003": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        }
                    }
                }
            },
            "seq050": {
                "shot020": {
                    "1": {
                        "1001": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        },
                        "1005": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        }
                    },
                    "2": {
                        "1002": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        },
                        "1003": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        }
                    }
                },
                "shot080": {
                    "1": {
                        "1010": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        },
                        "1050": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        }
                    },
                    "2": {
                        "1001": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        },
                        "1003": {
                            "time": {
                                "scene": 6761,
                                "render": 1551452,
                                "other": 152319
                            },
                            "utilization": {
                                19.343944549560548
                            }
                        }
                    }
                }
            }
        }

        # store the stats
        self.__stats = sorted(self.__data.values()[0].values()[0].values()[0].values()[0].keys())

    @property
    def stats(self):
        """
        a list of all stats stored. Every frame stores the same stats
        """
        return self.__stats

    def get_sequence_data(self, seq):
        """
        Gets the sequence render data.
        :param seq: a sequence in the format (seq###, ex: seq040)
        :return: a dictionary of shots and their render data or None if seq doesn't exist
        format returned is:
        {
            shot: {
                history: {
                    frame: {
                        stat: {
                            item(s)
                        }
                    }
                }
            },
            more shots...
        }
        """
        if seq in self.__data:
            return self.__data[seq]
        else:
            return None

    def get_shot_data(self, seq, shot, history=1):
        """
        Gets the
        :param seq: a sequence in the format (seq###, ex: seq040)
        :param shot: a shot in the format (shot###, ex: shot010)
        :param history: the render data to grab based off prior renders, default is latest, which is 1. accepts string
        or integer
            1 = latest
            2 = 2nd latest
            ...
            5 = 5th latest
        :return: a dictionary of frames and their render data or None if seq or shot or history doesn't exist
        format is {
            frame: {
                stat: {
                    item(s)
                }
            },
            frames...
        }
        """
        if isinstance(history, int):
            history = str(history)

        if seq in self.__data:
            if shot in self.__data[seq]:
                if history in self.__data[seq][shot]:
                    return self.__data[seq][shot][history]
        else:
            return None

